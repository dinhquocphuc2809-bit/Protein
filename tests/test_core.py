import asyncio
import hashlib
import hmac
import json
import secrets
import socket
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from backend.config import Settings
from backend.database import Database
from backend.providers import KeyPool, ProviderFailure, classify
from backend.security import Security
from backend.storage import Storage, public_addresses
from backend.subtitles import Cue, parse_srt, validate_cues, words_to_cues


@pytest.fixture
def core(tmp_path):
    settings = Settings(data_dir=tmp_path, master_key=secrets.token_hex(32), admin_token=secrets.token_hex(32),
                        reserve_free_bytes=0, disk_high_water=.94, cache_limit_bytes=150)
    db = Database(tmp_path / "test.sqlite3")
    return db, Security(db, settings), settings


def request(session, body=b"{}", nonce=None, timestamp=None, signed_body=None):
    timestamp = str(timestamp or int(time.time()))
    nonce = nonce or secrets.token_hex(16)
    message = "\n".join(["POST", "/v1/jobs", hashlib.sha256(signed_body if signed_body is not None else body).hexdigest(), timestamp, nonce])
    signature = hmac.new(bytes.fromhex(session["request_key"]), message.encode(), "sha256").hexdigest()
    headers = {"authorization": "Bearer " + session["token"], "x-auvirel-time": timestamp,
               "x-auvirel-nonce": nonce, "x-auvirel-signature": signature}
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}
    return Request({"type": "http", "method": "POST", "path": "/v1/jobs", "query_string": b"",
                    "scheme": "https", "server": ("test", 443), "headers": [(k.encode(), v.encode()) for k, v in headers.items()]}, receive)


def test_ticket_atomic_activation_and_revocation(core):
    db, security, _ = core
    ticket = security.create_ticket("parallel", 3600)
    with ThreadPoolExecutor(max_workers=4) as pool:
        sessions = list(pool.map(lambda _: security.activate(ticket["code"]), range(4)))
    assert len({s["ticket_expires"] for s in sessions}) == 1
    assert asyncio.run(security.authenticate(request(sessions[0]))) == ticket["id"]
    db.execute("UPDATE tickets SET active=0 WHERE id=?", (ticket["id"],))
    with pytest.raises(HTTPException) as error:
        asyncio.run(security.authenticate(request(sessions[0])))
    assert error.value.status_code == 401


def test_replay_body_tamper_and_clock(core):
    _, security, _ = core
    ticket = security.create_ticket("test", 3600)
    session = security.activate(ticket["code"])
    nonce = secrets.token_hex(16)
    asyncio.run(security.authenticate(request(session, nonce=nonce)))
    for req, status in [(request(session, nonce=nonce), 409), (request(session, body=b'{"changed":true}', signed_body=b"{}"), 401),
                        (request(session, timestamp=int(time.time())-120), 401), (request(session, timestamp=int(time.time())+120), 401)]:
        with pytest.raises(HTTPException) as error:
            asyncio.run(security.authenticate(req))
        assert error.value.status_code == status


def test_expiry_and_encryption(core):
    db, security, _ = core
    ticket = security.create_ticket("test", 60)
    security.activate(ticket["code"])
    db.execute("UPDATE tickets SET expires=? WHERE id=?", (time.time()-1, ticket["id"]))
    with pytest.raises(HTTPException):
        security.activate(ticket["code"])
    secret = "private-provider-value"
    encrypted = security.seal(secret)
    assert secret not in encrypted
    assert security.open(encrypted) == secret


def test_rotation_classifies_and_retries(core):
    db, security, _ = core
    pool = KeyPool(db, security)
    pool.add("tunelio", "a"*32)
    pool.add("tunelio", "b"*32)
    calls = []
    async def operation(key):
        calls.append(key)
        if len(calls) == 1:
            raise ProviderFailure("tunelio", 402, "depleted")
        return "media"
    assert asyncio.run(pool.run("tunelio", operation)) == "media"
    assert len(calls) == 2
    assert db.one("SELECT count(*) n FROM api_keys WHERE state='depleted'")["n"] == 1
    for code, expected in [(401, "invalid"), (402, "depleted"), (403, "forbidden"), (429, "cooling_down"), (500, "unavailable")]:
        with pytest.raises(ProviderFailure) as error:
            classify("test", httpx.Response(code, text="failure", headers={"Retry-After": "7"}))
        assert error.value.kind == expected


def test_modal_job_affinity_reuses_warm_account_and_fails_over(core):
    db, security, _ = core
    pool = KeyPool(db, security)
    for i in range(3):
        pool.add("modal", f"test-modal-account-{i:020d}")
    affinity, calls = {}, []
    async def ok(key):
        calls.append(key)
        return "aligned"
    async def run():
        for _ in range(3):
            assert await pool.run("modal", ok, affinity=affinity) == "aligned"
        assert len(set(calls)) == 1
        original = calls[0]
        async def exhausted(key):
            if key == original:
                raise ProviderFailure("modal", 402, "depleted")
            return await ok(key)
        assert await pool.run("modal", exhausted, affinity=affinity) == "aligned"
        assert calls[-1] != original
        await pool.run("modal", ok, affinity=affinity)
        assert calls[-1] == calls[-2]
        assert db.one("SELECT state FROM api_keys WHERE id=?", (affinity['modal'],))['state'] == 'available'
        assert db.one("SELECT count(*) n FROM api_keys WHERE state='depleted'")['n'] == 1
    asyncio.run(run())


def test_srt_validation_and_text():
    cues = parse_srt(b'1\r\n00:00:01,000 --> 00:00:03,200\r\n<b>Hello</b> &amp; goodbye\r\n')
    assert cues[0].text == "Hello & goodbye"
    assert cues[0].end == 3.2
    for data in [b'1\n00:61:00,000 --> 00:62:00,000\nhello', b'1\n00:00:03,000 --> 00:00:01,000\nhello', b"garbage", b"x"*(2*1024**2+1)]:
        with pytest.raises(ValueError):
            parse_srt(data)
    with pytest.raises(ValueError):
        validate_cues([Cue(id=0, start=0, end=1, text="a"), Cue(id=0, start=1, end=2, text="b")])
    with pytest.raises(ValueError):
        Cue(id=0, start=float("nan"), end=2, text="a")


def test_words_preserve_real_boundaries():
    cues = words_to_cues([{"word": "hello", "start": .4, "end": .8}, {"punctuated_word": "world.", "start": .9, "end": 1.5},
                         {"word": "next", "start": 3, "end": 3.5}])
    assert [(c.start, c.end) for c in cues] == [(.4, 1.5), (3, 3.5)]


@pytest.mark.parametrize("address", ["127.0.0.1", "169.254.169.254", "10.0.0.1", "100.100.100.100", "::1", "fd00::1", "::ffff:127.0.0.1"])
def test_ssrf_resolved_addresses(monkeypatch, address):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))])
    with pytest.raises(ValueError):
        public_addresses("https://example.org/audio")


@pytest.mark.parametrize("url", ["http://example.org", "https://user:pass@example.org", "https://example.org:444", "file:///etc/passwd"])
def test_ssrf_url_shape(url):
    with pytest.raises(ValueError):
        public_addresses(url)


def test_storage_reservation_and_lru(core):
    db, _, settings = core
    storage = Storage(db, settings)
    job = secrets.token_hex(16)
    with pytest.raises(RuntimeError):
        with storage.reserve(job, 1024) as path:
            (path / "partial").write_bytes(b"audio")
            raise RuntimeError("download interrupted")
    assert not (storage.spool / job).exists()
    assert not db.all("SELECT * FROM reservations")
    storage.put("a", "test", {"text": "a"*80})
    storage.put("b", "test", {"text": "b"*80})
    assert storage.get("a") is None
    assert storage.get("b")["text"] == "b"*80
    with pytest.raises(ValueError):
        with storage.reserve("../outside", 100):
            pytest.fail("Invalid reservation admitted")


def test_rotation_reaches_later_keys_and_transient_errors_recover(core):
    db, security, _ = core
    pool = KeyPool(db, security)
    for index in range(12):
        pool.add("tunelio", f"credential-{index:020d}")
    seen = []
    async def operation(key):
        seen.append(key)
        if len(seen) < 12:
            raise ProviderFailure("tunelio", 402, "depleted")
        return "success"
    assert asyncio.run(pool.run("tunelio", operation)) == "success"
    assert len(seen) == 12
    async def temporary(key):
        raise ProviderFailure("tunelio", 502, "invalid_json", retry_after=1)
    with pytest.raises(ProviderFailure):
        asyncio.run(pool.run("tunelio", temporary))
    assert db.one("SELECT count(*) n FROM api_keys WHERE state='cooling_down'")["n"] == 1
    assert not db.one("SELECT id FROM api_keys WHERE state='invalid_json'")
