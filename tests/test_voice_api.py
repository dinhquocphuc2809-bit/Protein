import asyncio
import base64
import io
from types import SimpleNamespace as NS
import wave

import httpx
import pytest

from gpu.voice_api import VoiceRegistry, create_api


def fixture():
    storage, calls, timeouts, cancelled = {}, [], [], []
    async def put(key, value, skip_if_exists=False):
        if skip_if_exists and key in storage:
            return False
        storage[key] = dict(value)
        return True
    async def get(key, default=None):
        value = storage.get(key, default)
        return dict(value) if value is not None else None
    async def pop(key, default=None):
        return storage.pop(key, default)
    async def spawn(*args):
        calls.append(args)
        await asyncio.sleep(.01)
        return NS(object_id='call-1')
    async def result(timeout):
        timeouts.append(timeout)
        return {'audio': b'OGG', 'duration': 1, 'voice_id': 'voice', 'timings': {'inference_seconds': .2}}
    async def cancel():
        cancelled.append(True)
    app = create_api(NS(put=NS(aio=put), get=NS(aio=get), pop=NS(aio=pop)),
                     lambda: NS(synthesize=NS(spawn=NS(aio=spawn))),
                     lambda _: NS(get=NS(aio=result), cancel=NS(aio=cancel)), 'test-revision')
    out = io.BytesIO()
    with wave.open(out, 'wb') as wav:
        wav.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
        wav.writeframes(bytes(16000))
    ref = {'reference': base64.b64encode(out.getvalue()).decode(), 'reference_text': 'Labelled voice fixture.'}
    return app, calls, timeouts, cancelled, ref


def test_registered_and_inline_requests_share_idempotency_without_reupload():
    async def run():
        app, calls, timeouts, cancelled, ref = fixture()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://voice.test') as client:
            health = (await client.get('/v1/health')).json()
            assert 'long_poll_v1' in health['capabilities']
            registration = await client.post('/v1/voices', json=ref)
            identity = registration.json()['reference_id']
            payload = {'text': 'A complete sentence.', 'language': 'vi', 'duration': None}
            headers = {'Idempotency-Key': 'a'*64}
            replies = await asyncio.gather(*[client.post('/v1/synthesize', json={**payload, 'reference_id':identity},headers=headers) for _ in range(2)])
            assert all(r.status_code==202 for r in replies)
            assert len(calls)==1
            inline = await client.post('/v1/synthesize',json={**payload,**ref},headers=headers)
            assert inline.status_code==202 and len(calls)==1
            conflict = await client.post('/v1/synthesize',json={**payload,'text':'Different.',**ref},headers=headers)
            assert conflict.status_code==409
            result = await client.get('/v1/results/'+'a'*64+'?wait=10')
            assert result.json()['state']=='done' and timeouts==[10]
            assert result.json()['timings']['inference_seconds']==.2
            await client.delete('/v1/results/'+'a'*64)
            assert cancelled and (await client.get('/v1/results/'+'a'*64)).status_code==410
    asyncio.run(run())


def test_lost_reference_requires_registration_before_spending_gpu():
    async def run():
        app, calls, _, _, ref = fixture()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://voice.test') as client:
            identity=(await client.post('/v1/voices',json=ref)).json()['reference_id']
            app.state.registry.items.clear()
            payload={'text':'Valid sentence.','reference_id':identity}
            response=await client.post('/v1/synthesize',json=payload,headers={'Idempotency-Key':'b'*64})
            assert response.status_code==404 and not calls
            await client.post('/v1/voices',json=ref)
            assert (await client.post('/v1/synthesize',json=payload,headers={'Idempotency-Key':'b'*64})).status_code==202
            assert len(calls)==1
    asyncio.run(run())


@pytest.mark.parametrize('mutation', [{'reference':'invalid'}, {'reference_text':''}, {'extra':True}])
def test_invalid_registration_does_not_reach_gpu(mutation):
    async def run():
        app,calls,_,_,ref=fixture()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://voice.test') as client:
            assert (await client.post('/v1/voices',json={**ref,**mutation})).status_code==400
            assert not calls
    asyncio.run(run())


def test_registry_limits_and_expiration():
    registry=VoiceRegistry(max_bytes=12,max_items=2,ttl=900)
    registry.put('a',b'1234','a');registry.put('b',b'1234','b')
    registry.get('a');registry.put('c',b'1234','c')
    assert set(registry.items)=={'a','c'} and registry.size==10
    registry.ttl=-1
    registry.prune()
    assert not registry.items and registry.size==0


def test_wait_is_bounded_and_cancel_waits_for_submission_then_sticks():
    async def run():
        app,calls,_,cancelled,ref=fixture()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://voice.test') as client:
            for value in ['13','-1','nan','inf']:
                assert (await client.get('/v1/results/'+'a'*64+'?wait='+value)).status_code==422
            submission=asyncio.create_task(client.post('/v1/synthesize',json={'text':'Test.',**ref},headers={'Idempotency-Key':'a'*64}))
            while not calls:await asyncio.sleep(0)
            cancellation=await client.delete('/v1/results/'+'a'*64)
            assert (await submission).status_code==202 and cancellation.status_code==200
            assert cancelled and (await client.get('/v1/results/'+'a'*64)).status_code==410
    asyncio.run(run())
