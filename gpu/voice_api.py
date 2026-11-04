"""Authenticated Modal CPU ingress; reusable references and bounded result waits.

Proxy authentication is enforced by the Modal decorator in tts.py, before this app.
"""
import asyncio
import base64
import binascii
from collections import OrderedDict
import hashlib
import io
import json
import re
import time
import wave
import weakref

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse


def reference(data):
    try:
        text = data['reference_text']
        if not isinstance(text, str) or not 1 <= len(text) <= 1200 or not text.strip():
            raise ValueError()
        audio = base64.b64decode(data['reference'], validate=True)
        if not 44 <= len(audio) <= 4*1024**2 or audio[:4] != b'RIFF' or audio[8:12] != b'WAVE':
            raise ValueError()
        with wave.open(io.BytesIO(audio)) as wav:
            if (not 8000 <= wav.getframerate() <= 96000 or wav.getnchannels() not in (1, 2)
                    or wav.getsampwidth() != 2 or not 1 <= wav.getnframes()/wav.getframerate() <= 30
                    or len(wav.readframes(wav.getnframes())) != wav.getnframes()*wav.getnchannels()*2):
                raise ValueError()
        identity = hashlib.sha256(audio + text.encode()).hexdigest()
        return identity, audio, text
    except (KeyError, TypeError, ValueError, binascii.Error, wave.Error, EOFError):
        raise HTTPException(400, 'Invalid reference WAV or transcript') from None


class VoiceRegistry:
    def __init__(self, max_bytes=16*1024**2, max_items=32, ttl=900):
        self.items = OrderedDict()
        self.max_bytes, self.max_items, self.ttl = max_bytes, max_items, ttl
        self.size = 0

    def prune(self):
        now = time.monotonic()
        for key, (audio, text, touched) in list(self.items.items()):
            if now-touched > self.ttl:
                self.items.pop(key)
                self.size -= len(audio) + len(text.encode())

    def put(self, identity, audio, text):
        self.prune()
        size = len(audio) + len(text.encode())
        if size > self.max_bytes:
            raise HTTPException(413, 'Reference exceeds registry capacity')
        previous = self.items.pop(identity, None)
        if previous:
            self.size -= len(previous[0]) + len(previous[1].encode())
        self.items[identity] = (audio, text, time.monotonic())
        self.size += size
        while self.size > self.max_bytes or len(self.items) > self.max_items:
            _, old = self.items.popitem(last=False)
            self.size -= len(old[0]) + len(old[1].encode())

    def get(self, identity):
        self.prune()
        value = self.items.pop(identity, None)
        if value is None:
            raise HTTPException(404, 'Reference expired; register the voice again')
        self.items[identity] = (*value[:2], time.monotonic())
        return value[:2]


def create_api(store, worker, call_from_id, revision):
    web = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    registry = VoiceRegistry()
    web.state.registry = registry
    locks = weakref.WeakValueDictionary()

    def lock_for(identity):
        lock = locks.get(identity)
        if lock is None:
            lock = locks[identity] = asyncio.Lock()
        return lock

    async def body(request):
        result = bytearray()
        try:
            async with asyncio.timeout(20):
                async for chunk in request.stream():
                    result.extend(chunk)
                    if len(result) > 6*1024**2:
                        raise HTTPException(413, 'Request too large')
            value = json.loads(result)
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except TimeoutError:
            raise HTTPException(408, 'Request body timed out') from None
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(400, 'Invalid JSON object') from None

    @web.get('/v1/health')
    async def health():
        return {'ok': True, 'engine': 'omnivoice', 'revision': revision, 'single_voice': True,
                'capabilities': ['voice_registry_v1', 'long_poll_v1']}

    @web.post('/v1/voices')
    async def register(request: Request):
        data = await body(request)
        if set(data) != {'reference', 'reference_text'}:
            raise HTTPException(400, 'Expected reference and reference_text')
        identity, audio, text = reference(data)
        registry.put(identity, audio, text)
        return {'reference_id': identity, 'expires_in': registry.ttl}

    @web.post('/v1/synthesize', status_code=202)
    async def synthesize(request: Request):
        started = time.perf_counter()
        data = await body(request)
        uploaded = time.perf_counter()
        try:
            if set(data) - {'text', 'reference', 'reference_text', 'reference_id', 'duration', 'language'}:
                raise ValueError()
            text, language, duration = data['text'], data.get('language', 'vi'), data.get('duration')
            if not isinstance(text, str) or not 1 <= len(text.strip()) <= 800:
                raise ValueError()
            if not isinstance(language, str) or not re.fullmatch(r'[a-z]{2,3}', language):
                raise ValueError()
            if duration is not None and (type(duration) not in (int, float) or not .2 <= duration <= 30):
                raise ValueError()
            if 'reference_id' in data:
                if 'reference' in data or 'reference_text' in data or not re.fullmatch(r'[a-f0-9]{64}', data['reference_id']):
                    raise ValueError()
                audio, ref_text = registry.get(data['reference_id'])
                data = {k: v for k, v in data.items() if k != 'reference_id'}
                data.update(reference=base64.b64encode(audio).decode(), reference_text=ref_text)
            else:
                _, audio, ref_text = reference(data)
        except (KeyError, TypeError, ValueError):
            raise HTTPException(400, 'Invalid single-voice synthesis input') from None
        identity = request.headers.get('Idempotency-Key', '')
        if not re.fullmatch(r'[a-f0-9]{64}', identity):
            raise HTTPException(400, 'A SHA-256 Idempotency-Key is required')
        fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        validated = time.perf_counter()
        async with lock_for(identity):
            entry = {'hash': fingerprint, 'created': time.time(), 'call': None}
            inserted = await store.put.aio(identity, entry, skip_if_exists=True)
            claimed = time.perf_counter()
            if not inserted:
                entry = await store.get.aio(identity)
                if entry['hash'] != fingerprint:
                    raise HTTPException(409, 'Idempotency input mismatch')
                if entry.get('cancelled'):
                    raise HTTPException(410, 'Synthesis was cancelled; create a new attempt')
                if not entry['call']:
                    raise HTTPException(409, 'Submission in progress; poll this synthesis ID')
                return {'id': identity}
            # A crashed submission remains indeterminate rather than spending GPU twice.
            call = await worker().synthesize.spawn.aio(text, audio, ref_text, duration, language)
            spawned = time.perf_counter()
            entry['call'] = call.object_id
            await store.put.aio(identity, entry)
            saved = time.perf_counter()
            return {'id': identity, 'timings': {'body_seconds': uploaded-started,
                    'validation_seconds': validated-uploaded, 'claim_seconds': claimed-validated,
                    'spawn_seconds': spawned-claimed, 'save_seconds': saved-spawned,
                    'submission_seconds': saved-started}}

    async def lookup(identity):
        if not re.fullmatch(r'[a-f0-9]{64}', identity):
            raise HTTPException(400, 'Invalid synthesis ID')
        entry = await store.get.aio(identity, None)
        if entry is None:
            raise HTTPException(404, 'Synthesis not found')
        if time.time()-entry['created'] > 48*3600:
            await store.pop.aio(identity, None)
            raise HTTPException(410, 'Synthesis result expired')
        if entry.get('cancelled'):
            raise HTTPException(410, 'Synthesis cancelled')
        if not entry['call'] and time.time()-entry['created'] > 120:
            raise HTTPException(503, 'Submission interrupted; create a new attempt')
        return entry

    @web.get('/v1/results/{call_id}')
    async def result(call_id: str, wait: float = Query(default=0, ge=0, le=12, allow_inf_nan=False)):
        entry = await lookup(call_id)
        if not entry['call']:
            return JSONResponse({'state': 'pending'}, 202)
        try:
            value = await call_from_id(entry['call']).get.aio(timeout=wait)
        except TimeoutError:
            return JSONResponse({'state': 'pending'}, 202)
        except Exception:
            return JSONResponse({'state': 'failed', 'error': 'Voice synthesis failed; retry with a shorter cue or reference'}, 502)
        await lookup(call_id)
        if not isinstance(value, dict) or not isinstance(value.get('audio'), bytes):
            raise HTTPException(502, 'Invalid synthesis result')
        return {'state': 'done', 'audio': base64.b64encode(value['audio']).decode(), 'mime': 'audio/ogg',
                'duration': value['duration'], 'voice_id': value['voice_id'], 'timings': value.get('timings', {})}

    @web.delete('/v1/results/{call_id}')
    async def cancel(call_id: str):
        async with lock_for(call_id):
            entry = await lookup(call_id)
            entry['cancelled'] = True
            await store.put.aio(call_id, entry)
            if entry['call']:
                await call_from_id(entry['call']).cancel.aio()
        return {'state': 'cancelled'}

    return web
