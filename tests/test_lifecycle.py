import asyncio
import io
import json
import secrets
import threading
import time
import wave

import httpx
import pytest

from backend.app import BodyLimit, build
from backend.config import Settings
from backend.jobs import JobCancelled, audio_windows, download_owned
from backend.storage import Storage, download_public
from test_core import request


def settings(tmp_path):
    return Settings(data_dir=tmp_path, master_key=secrets.token_hex(32), admin_token=secrets.token_hex(32),
                    reserve_free_bytes=0, disk_high_water=.94)


def test_signed_http_and_private_admin(tmp_path):
    app = build(settings(tmp_path))
    ticket = app.state.security.create_ticket("integration", 3600)
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test") as client:
            login = await client.post("/v1/session", json={"code": ticket["code"]})
            assert login.status_code == 200
            body = json.dumps({"url": "https://example.org/video", "cues": [{"id": 0, "start": 0, "end": 2, "text": "Hello"}]}).encode()
            headers = dict(request(login.json(), body).headers)
            headers.update({"content-type": "application/json", "idempotency-key": "integration-request-01"})
            first = await client.post("/v1/jobs", content=body, headers=headers)
            assert first.status_code == 202, first.text
            assert (await client.post("/v1/jobs", content=body, headers=headers)).status_code == 409
            headers.update(dict(request(login.json(), body).headers))
            again = await client.post("/v1/jobs", content=body, headers=headers)
            assert again.json()["id"] == first.json()["id"]
            assert (await client.get("/admin/tickets")).status_code == 404
            app.state.db.execute("UPDATE tickets SET active=0 WHERE id=?", (ticket["id"],))
            headers.update(dict(request(login.json(), body).headers))
            assert (await client.post("/v1/jobs", content=body, headers=headers)).status_code == 401
        await app.state.jobs.close()
    asyncio.run(run())


def test_body_size_and_slow_sender():
    async def run():
        output = []
        async def forbidden(*args):
            pytest.fail("Oversized or timed-out body reached application")
        async def send(message):
            output.append(message)
        async def large():
            return {"type": "http.request", "body": b"12345", "more_body": False}
        async def slow():
            await asyncio.sleep(1)
        for receive, expected in [(large, 413), (slow, 408)]:
            output.clear()
            await BodyLimit(forbidden, limit=4, timeout=.01)({"type": "http"}, receive, send)
            assert output[0]["status"] == expected
    asyncio.run(run())


def test_download_preserves_existing_file(tmp_path, monkeypatch):
    import backend.storage as module
    path = tmp_path / "original"
    path.write_bytes(b"irreplaceable")
    monkeypatch.setattr(module, "public_addresses", lambda url: (_ for _ in ()).throw(ValueError("bad URL")))
    with pytest.raises(ValueError):
        download_public("https://example.org", path, 100)
    assert path.read_bytes() == b"irreplaceable"


def test_cancel_joins_download_before_cleanup(tmp_path, monkeypatch):
    import backend.jobs as module
    started, finished = threading.Event(), threading.Event()
    path = tmp_path / "download"
    def download(url, dest, limit, deadline, progress, cancelled):
        started.set()
        assert cancelled.wait(2)
        time.sleep(.02)
        dest.write_bytes(b"last write")
        finished.set()
        raise InterruptedError()
    monkeypatch.setattr(module, "download_public", download)
    async def run():
        task = asyncio.create_task(download_owned("https://example.org", path, 100, None))
        await asyncio.to_thread(started.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finished.is_set()
    asyncio.run(run())


@pytest.mark.parametrize("seconds", [1, 27, 28, 29, 51, 52, 53, 80])
def test_audio_overlap_covers_entire_input(tmp_path, seconds):
    path = tmp_path / "audio.wav"
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        output.writeframes(b"\0\0"*(16000*seconds))
    windows = list(audio_windows(path, 100))
    assert windows[0][2] == 0
    assert windows[-1][3] > seconds
    for index, (data, offset, start, end) in enumerate(windows):
        with wave.open(io.BytesIO(data)) as wav:
            assert wav.getnframes()/16000 <= 28
        if index:
            assert windows[index-1][3] == start


def test_guard_cancels_work_after_revocation(tmp_path):
    app = build(settings(tmp_path))
    security, jobs, db = app.state.security, app.state.jobs, app.state.db
    ticket = security.create_ticket("cancel", 3600)
    security.activate(ticket["code"])
    job = jobs.submit(ticket["id"], "video", {}, "cancellation-test-01")
    db.execute("UPDATE jobs SET state='running' WHERE id=?", (job["id"],))
    job["ticket_id"] = ticket["id"]
    stopped = []
    async def run():
        async def work():
            try:
                await asyncio.sleep(30)
            finally:
                stopped.append(True)
        task = asyncio.create_task(jobs.guarded(job, work()))
        await asyncio.sleep(.01)
        db.execute("UPDATE jobs SET state='cancelled' WHERE id=?", (job["id"],))
        with pytest.raises(JobCancelled):
            await task
        assert stopped
        await jobs.close()
    asyncio.run(run())


def test_renewal_never_extends_ticket_lifetime(tmp_path):
    app = build(settings(tmp_path))
    security = app.state.security
    ticket = security.create_ticket("renew", 3600)
    first = security.activate(ticket["code"])
    renewed = security.renew(ticket["id"])
    assert renewed["token"] != first["token"]
    assert renewed["ticket_expires"] == first["ticket_expires"]
    assert renewed["expires"] <= first["ticket_expires"]
    app.state.db.execute("UPDATE tickets SET active=0 WHERE id=?", (ticket["id"],))
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        security.renew(ticket["id"])
    asyncio.run(app.state.jobs.close())
