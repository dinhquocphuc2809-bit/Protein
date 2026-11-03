from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time

from cryptography.fernet import Fernet
from fastapi import HTTPException, Request

from .config import Settings
from .database import Database


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class Security:
    def __init__(self, db: Database, settings: Settings):
        self.db, self.settings = db, settings
        self.master = settings.master_key.get_secret_value().encode()
        key = hmac.digest(self.master, b"auvirel-encryption-v1", "sha256")
        self.cipher = Fernet(base64.urlsafe_b64encode(key))

    def seal(self, text: str) -> str:
        return self.cipher.encrypt(text.encode()).decode()

    def open(self, text: str) -> str:
        return self.cipher.decrypt(text.encode()).decode()

    def ticket_hash(self, code: str) -> str:
        return hmac.new(self.master, b"ticket:" + code.encode(), "sha256").hexdigest()

    def rate_limit(self, scope: str, count: int, period: int):
        bucket = int(time.time()) // period
        with self.db.transaction() as conn:
            conn.execute("INSERT INTO rate_limits VALUES(?,?,1) ON CONFLICT(scope,bucket) DO UPDATE SET count=count+1", (scope, bucket))
            actual = conn.execute("SELECT count FROM rate_limits WHERE scope=? AND bucket=?", (scope, bucket)).fetchone()[0]
        if actual > count:
            raise HTTPException(429, "Rate limit exceeded", headers={"Retry-After": str(period)})

    def create_ticket(self, label: str, duration: int) -> dict:
        if not 60 <= duration <= 366 * 86400 or len(label) > 120:
            raise ValueError("Invalid ticket label or duration")
        code = "AV-" + secrets.token_urlsafe(24)
        ticket_id = secrets.token_hex(16)
        self.db.execute("INSERT INTO tickets(id,code_hash,label,duration,created) VALUES(?,?,?,?,?)",
                        (ticket_id, self.ticket_hash(code), label, duration, time.time()))
        return {"id": ticket_id, "code": code, "duration": duration}

    def activate(self, code: str) -> dict:
        now = time.time()
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM tickets WHERE code_hash=?", (self.ticket_hash(code),)).fetchone()
            if not row or not row["active"] or row["expires"] is not None and row["expires"] <= now:
                raise HTTPException(401, "Invalid or expired access code")
            expiry = row["expires"] or now + row["duration"]
            if row["activated"] is None:
                conn.execute("UPDATE tickets SET activated=?,expires=? WHERE id=?", (now, expiry, row["id"]))
            session_id, request_key = secrets.token_hex(24), secrets.token_hex(32)
            session_expiry = min(expiry, now + self.settings.session_seconds)
            conn.execute("INSERT INTO sessions VALUES(?,?,?,?)", (session_id, row["id"], self.seal(request_key), session_expiry))
        signature = hmac.new(self.master, b"session:" + session_id.encode(), "sha256").hexdigest()
        return {"token": session_id + "." + signature, "request_key": request_key,
                "expires": session_expiry, "ticket_expires": expiry, "server_time": now}

    def check_ticket(self, ticket_id: str):
        row = self.db.one("SELECT * FROM tickets WHERE id=?", (ticket_id,))
        if not row or not row["active"] or not row["expires"] or row["expires"] <= time.time():
            raise HTTPException(401, "Ticket expired or revoked")
        return row

    def renew(self, ticket_id: str):
        ticket = self.check_ticket(ticket_id)
        now = time.time()
        session_id, request_key = secrets.token_hex(24), secrets.token_hex(32)
        expiry = min(ticket["expires"], now+self.settings.session_seconds)
        self.db.execute("INSERT INTO sessions VALUES(?,?,?,?)", (session_id, ticket_id, self.seal(request_key), expiry))
        signature = hmac.new(self.master, b"session:"+session_id.encode(), "sha256").hexdigest()
        return {"token": session_id+"."+signature, "request_key": request_key, "expires": expiry,
                "ticket_expires": ticket["expires"], "server_time": now}

    async def authenticate(self, request: Request) -> str:
        auth = request.headers.get("authorization", "")
        match = re.fullmatch(r"Bearer ([a-f0-9]{48})\.([a-f0-9]{64})", auth)
        if not match:
            raise HTTPException(401, "Missing session")
        session_id, signature = match.groups()
        expected = hmac.new(self.master, b"session:" + session_id.encode(), "sha256").hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(401, "Invalid session")
        row = self.db.one("SELECT * FROM sessions WHERE id=?", (session_id,))
        if not row or row["expires"] <= time.time():
            raise HTTPException(401, "Session expired")
        self.check_ticket(row["ticket_id"])
        timestamp, nonce = request.headers.get("x-auvirel-time", ""), request.headers.get("x-auvirel-nonce", "")
        if not re.fullmatch(r"\d{10}", timestamp) or abs(time.time() - int(timestamp)) > 60 or not re.fullmatch(r"[a-f0-9]{32}", nonce):
            raise HTTPException(401, "Invalid request time or nonce")
        target = request.url.path + ("?" + request.url.query if request.url.query else "")
        message = "\n".join([request.method, target, digest(await request.body()), timestamp, nonce])
        key = bytes.fromhex(self.open(row["secret"]))
        expected = hmac.new(key, message.encode(), "sha256").hexdigest()
        if not hmac.compare_digest(expected, request.headers.get("x-auvirel-signature", "")):
            raise HTTPException(401, "Invalid request signature")
        try:
            self.db.execute("INSERT INTO nonces VALUES(?,?,?)", (session_id, nonce, time.time() + 120))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Request replay rejected") from None
        self.rate_limit("ticket:" + row["ticket_id"], 120, 60)
        return row["ticket_id"]

    def admin(self, request: Request):
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        if not hmac.compare_digest(token.encode(), self.settings.admin_token.get_secret_value().encode()):
            raise HTTPException(401, "Admin authentication required")
