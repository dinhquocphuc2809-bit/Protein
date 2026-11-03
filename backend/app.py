from __future__ import annotations

import asyncio
import json
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path

import psutil
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .config import Settings
from .database import Database
from .jobs import Jobs, VideoRequest
from .providers import KeyPool, Providers
from .security import Security, canonical
from .storage import Storage


class BodyLimit:
    def __init__(self, app, limit=3*1024**2, timeout=20):
        self.app, self.limit, self.timeout = app, limit, timeout

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        chunks, count = [], 0
        deadline = asyncio.get_running_loop().time() + self.timeout
        while True:
            try:
                message = await asyncio.wait_for(receive(), max(0, deadline-asyncio.get_running_loop().time()))
            except TimeoutError:
                return await JSONResponse({"detail": "Request body timed out"}, status_code=408)(scope, receive, send)
            if message["type"] == "http.disconnect":
                return
            count += len(message.get("body", b""))
            if count > self.limit:
                return await JSONResponse({"detail": "Request body too large"}, status_code=413)(scope, receive, send)
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        delivered = False
        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()
        await self.app(scope, bounded_receive, send)


class Login(BaseModel):
    code: str = Field(min_length=16, max_length=100)


class StudyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    video_job_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    model: str = Field(default="basic", pattern=r"^(basic|advanced|deepseek)$")
    question: str = Field(default="", max_length=4000)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=12)


class TicketCreate(BaseModel):
    label: str = Field(max_length=120)
    duration: int = Field(ge=60, le=366*86400)


class TicketEdit(BaseModel):
    active: bool | None = None
    extend_seconds: int = Field(default=0, ge=0, le=366*86400)


class KeyImport(BaseModel):
    provider: str
    values: list[str] = Field(min_length=1, max_length=200)
    label: str = Field(default="", max_length=80)


def build(settings: Settings | None = None, *, admin=False) -> FastAPI:
    settings = settings or Settings()
    db = Database(settings.data_dir / "auvirel.sqlite3")
    security = Security(db, settings)
    storage = Storage(db, settings)
    pool = KeyPool(db, security)
    providers = Providers(pool, settings)
    jobs = Jobs(db, security, storage, providers, settings)

    @asynccontextmanager
    async def lifespan(app):
        if not admin:
            await jobs.start()
        try:
            yield
        finally:
            balance_task = getattr(app.state, "balance_task", None)
            if balance_task:
                balance_task.cancel()
                await asyncio.gather(balance_task, return_exceptions=True)
            await jobs.close()

    app = FastAPI(title="Auvirel Admin" if admin else "Auvirel API", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)
    app.state.db, app.state.security, app.state.jobs = db, security, jobs
    app.add_middleware(BodyLimit)
    if settings.allowed_origins:
        app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_methods=["GET", "POST", "PATCH", "DELETE"],
                           allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Auvirel-Time", "X-Auvirel-Nonce", "X-Auvirel-Signature"])

    @app.middleware("http")
    async def guards(request, call_next):
        try:
            security.rate_limit("ip:" + (request.client.host if request.client else "unknown"), 300 if not admin else 600, 60)
        except HTTPException as error:
            return JSONResponse({"detail": error.detail}, error.status_code, headers=error.headers)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
        return response

    @app.exception_handler(ValueError)
    async def invalid_input(request, error):
        return JSONResponse({"detail": str(error)[:240]}, status_code=400)

    @app.get("/healthz")
    def health():
        db.one("SELECT 1")
        return {"ok": True, "service": "admin" if admin else "api", "version": "0.1.0"}

    if not admin:
        @app.post("/v1/session")
        def login(body: Login, request: Request):
            security.rate_limit("login:" + (request.client.host if request.client else "unknown"), 10, 60)
            return security.activate(body.code)

        @app.get("/v1/session")
        def session(ticket: str = Depends(security.authenticate)):
            data = security.check_ticket(ticket)
            return {"ticket_id": ticket, "expires": data["expires"], "server_time": time.time()}

        @app.post("/v1/session/refresh")
        def refresh_session(ticket: str = Depends(security.authenticate)):
            return security.renew(ticket)

        @app.post("/v1/jobs", status_code=202)
        def create_job(body: VideoRequest, ticket: str = Depends(security.authenticate), idempotency_key: str = Header()):
            return jobs.submit(ticket, "video", body.model_dump(), idempotency_key)

        @app.get("/v1/jobs/{job_id}")
        def get_job(job_id: str, ticket: str = Depends(security.authenticate)):
            return jobs.get(ticket, job_id)

        @app.delete("/v1/jobs/{job_id}")
        def cancel_job(job_id: str, ticket: str = Depends(security.authenticate)):
            jobs.get(ticket, job_id)
            db.execute("UPDATE jobs SET state='cancelled',stage='cancelled',updated=? WHERE id=? AND ticket_id=? AND state IN ('queued','running')", (time.time(), job_id, ticket))
            return jobs.get(ticket, job_id)

        @app.post("/v1/summary", status_code=202)
        def summary(body: StudyRequest, ticket: str = Depends(security.authenticate), idempotency_key: str = Header()):
            return jobs.submit(ticket, "summary", body.model_dump(), idempotency_key)

        @app.post("/v1/chat", status_code=202)
        def chat(body: StudyRequest, ticket: str = Depends(security.authenticate), idempotency_key: str = Header()):
            if not body.question.strip() or any(set(m) != {"role", "content"} or m["role"] not in {"user", "assistant"} or len(m["content"]) > 8000 for m in body.history):
                raise HTTPException(400, "Invalid question/history")
            return jobs.submit(ticket, "chat", body.model_dump(), idempotency_key)

        @app.get("/v1/models")
        def models(ticket: str = Depends(security.authenticate)):
            return {"basic": settings.model_basic, "advanced": settings.model_advanced, "deepseek": settings.model_deepseek,
                    "overrides": {r["key"]: json.loads(r["value"]) for r in db.all("SELECT * FROM config WHERE key LIKE 'model_%'")}}
        return app

    dependencies = [Depends(security.admin)]
    static = Path(__file__).parent / "admin"

    @app.get("/")
    def dashboard():
        return FileResponse(static / "index.html")

    @app.get("/admin.js")
    def javascript():
        return FileResponse(static / "admin.js", media_type="application/javascript")

    @app.get("/admin.css")
    def stylesheet():
        return FileResponse(static / "admin.css", media_type="text/css")

    @app.get("/admin/stats", dependencies=dependencies)
    def stats():
        disk, memory = psutil.disk_usage(str(settings.data_dir)), psutil.virtual_memory()
        return {"system": {"cpu_percent": psutil.cpu_percent(), "memory_used": memory.used, "memory_total": memory.total,
                           "disk_used": disk.used, "disk_total": disk.total, "disk_free": disk.free},
                "jobs": db.all("SELECT state,count(*) count FROM jobs GROUP BY state"),
                "cache": db.one("SELECT count(*) entries,coalesce(sum(bytes),0) bytes FROM cache"),
                "cache_events": db.all("SELECT event,count(*) count FROM usage WHERE provider='cache' GROUP BY event"),
                "usage": db.all("SELECT provider,event,count(*) calls,sum(amount) amount FROM usage GROUP BY provider,event")}

    @app.get("/admin/tickets", dependencies=dependencies)
    def tickets():
        return db.all("""SELECT t.id,t.label,t.duration,t.activated,t.expires,t.active,t.created,
                      (SELECT count(*) FROM jobs j WHERE j.ticket_id=t.id) jobs,
                      (SELECT coalesce(sum(amount),0) FROM usage u WHERE u.ticket_id=t.id AND event='asr_seconds') asr_seconds,
                      (SELECT coalesce(sum(amount),0) FROM usage u WHERE u.ticket_id=t.id AND event='translate') translated_cues,
                      (SELECT count(*) FROM usage u WHERE u.ticket_id=t.id AND provider='cache' AND event='hit') cache_hits
                      FROM tickets t ORDER BY created DESC LIMIT 1000""")

    @app.post("/admin/tickets", dependencies=dependencies)
    def create_ticket(body: TicketCreate):
        return security.create_ticket(body.label, body.duration)

    @app.patch("/admin/tickets/{ticket_id}", dependencies=dependencies)
    def edit_ticket(ticket_id: str, body: TicketEdit):
        with db.transaction() as conn:
            row = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
            if not row:
                raise HTTPException(404, "Ticket not found")
            if body.active is not None:
                conn.execute("UPDATE tickets SET active=? WHERE id=?", (int(body.active), ticket_id))
            if body.extend_seconds:
                if row["activated"] is None:
                    conn.execute("UPDATE tickets SET duration=duration+? WHERE id=?", (body.extend_seconds, ticket_id))
                else:
                    conn.execute("UPDATE tickets SET expires=? WHERE id=?", (max(time.time(), row["expires"]) + body.extend_seconds, ticket_id))
        return {"ok": True}

    @app.delete("/admin/tickets/{ticket_id}", dependencies=dependencies)
    def delete_ticket(ticket_id: str):
        # Tombstone preserves accounting and foreign-key integrity.
        changed = db.execute("UPDATE tickets SET active=0,label='[deleted]',code_hash=? WHERE id=?", ("deleted:" + ticket_id, ticket_id))
        if not changed:
            raise HTTPException(404, "Ticket not found")
        return {"ok": True}

    @app.get("/admin/keys", dependencies=dependencies)
    def keys():
        return db.all("SELECT id,provider,label,state,cooldown,balance,checked,last_error,calls FROM api_keys ORDER BY provider,label")

    @app.post("/admin/keys", dependencies=dependencies)
    def add_keys(body: KeyImport):
        normalized = []
        for i, value in enumerate(body.values):
            value = value.strip()
            if body.provider == "modal":
                token_id = re.search(r"--token-id\s+([A-Za-z0-9_-]+)", value)
                token_secret = re.search(r"--token-secret\s+([A-Za-z0-9_-]+)", value)
                if token_id and token_secret:
                    value = canonical({"token_id": token_id[1], "token_secret": token_secret[1]})
                else:
                    credentials = json.loads(value)
                    if not isinstance(credentials, dict) or set(credentials) != {"token_id", "token_secret"}:
                        raise ValueError("Expected Modal token_id and token_secret")
                credentials = json.loads(value)
                if not all(isinstance(credentials[k], str) and re.fullmatch(prefix+r"[A-Za-z0-9_-]+", credentials[k]) for k, prefix in [("token_id", "ak-"), ("token_secret", "as-")]):
                    raise ValueError("Invalid Modal token format")
            if body.provider not in pool.PROVIDERS or not 16 <= len(value) <= 4096:
                raise ValueError("Invalid provider or credential")
            normalized.append(value)
        for i, value in enumerate(normalized):
            pool.add(body.provider, value, f"{body.label} {i+1}".strip())
        return {"ok": True, "processed": len(body.values)}

    @app.post("/admin/keys/{key_id}/enable", dependencies=dependencies)
    def enable_key(key_id: str):
        db.execute("UPDATE api_keys SET state='available',cooldown=0,last_error=NULL WHERE id=?", (key_id,))
        return {"ok": True}

    @app.post("/admin/balances", dependencies=dependencies, status_code=202)
    async def refresh_balances():
        task = getattr(app.state, "balance_task", None)
        if task is None or task.done():
            app.state.balance_task = asyncio.create_task(providers.refresh_balances())
        return {"ok": True, "state": "refreshing"}

    @app.delete("/admin/keys/{key_id}", dependencies=dependencies)
    def remove_key(key_id: str):
        db.execute("DELETE FROM api_keys WHERE id=?", (key_id,))
        return {"ok": True}

    @app.get("/admin/jobs", dependencies=dependencies)
    def history():
        return db.all("SELECT id,ticket_id,kind,state,stage,error,created,updated,json_extract(result,'$.title') title FROM jobs ORDER BY created DESC LIMIT 200")

    @app.get("/admin/models", dependencies=dependencies)
    async def model_catalog():
        async def gemini(key):
            response = await providers.request("gemini", "GET", "https://generativelanguage.googleapis.com/v1beta/models", headers={"x-goog-api-key": key}, params={"pageSize": 1000})
            return [m["name"].removeprefix("models/") for m in response.get("models", [])]
        async def deepseek(key):
            response = await providers.request("deepseek", "GET", "https://api.deepseek.com/models", headers={"Authorization": "Bearer " + key})
            return [m["id"] for m in response.get("data", [])]
        return {"gemini": await pool.run("gemini", gemini), "deepseek": await pool.run("deepseek", deepseek)}

    @app.post("/admin/models", dependencies=dependencies)
    async def model_config(body: dict[str, str]):
        catalog = await model_catalog()
        for selection, model in body.items():
            if selection not in {"basic", "advanced", "deepseek"} or model not in catalog["deepseek" if selection == "deepseek" else "gemini"]:
                raise HTTPException(400, "Model not available from the official provider")
        with db.transaction() as conn:
            for selection, model in body.items():
                conn.execute("INSERT OR REPLACE INTO config VALUES(?,?)", ("model_" + selection, canonical(model)))
        return {"ok": True}
    return app


def create_public_app():
    return build()


def create_admin_app():
    return build(admin=True)
