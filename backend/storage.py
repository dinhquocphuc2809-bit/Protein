from __future__ import annotations

import contextlib
import http.client
import ipaddress
import json
import os
import re
import shutil
import socket
import ssl
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from .config import Settings
from .database import Database


def public_addresses(url: str) -> tuple[str, list[str]]:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443) or not parsed.hostname:
        raise ValueError("Only public HTTPS URLs on port 443 are supported")
    host = parsed.hostname.encode("idna").decode()
    addresses = list(dict.fromkeys(item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)))
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("Media URL resolves to a nonpublic network")
    return host, addresses


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host: str, address: str):
        super().__init__(host, timeout=30, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        # Pin the validated IP, while keeping the original TLS SNI and certificate name.
        raw = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def download_public(url: str, destination: Path, max_bytes: int, deadline_seconds=180, progress=None, cancelled=None) -> int:
    started = time.monotonic()
    created = False
    def check():
        if cancelled is not None and cancelled.is_set():
            raise InterruptedError("Media download cancelled")
        if time.monotonic() - started > deadline_seconds:
            raise ValueError("Media download time limit exceeded")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        for _ in range(5):
            check()
            host, addresses = public_addresses(url)
            parsed = urlsplit(url)
            target = parsed.path or "/"
            if parsed.query:
                target += "?" + parsed.query
            connection = PinnedHTTPS(host, addresses[0])
            connection.timeout = min(5, max(.1, deadline_seconds - (time.monotonic()-started)))
            try:
                connection.request("GET", target, headers={"User-Agent": "Auvirel/0.1", "Accept-Encoding": "identity"})
                response = connection.getresponse()
                if response.status in (301, 302, 303, 307, 308):
                    location = response.getheader("Location")
                    if not location:
                        raise ValueError("Media redirect has no destination")
                    url = urljoin(url, location)
                    continue
                if response.status != 200:
                    raise ValueError(f"Media server returned HTTP {response.status}")
                length = response.getheader("Content-Length")
                if length and (not length.isdigit() or int(length) > max_bytes):
                    raise ValueError("Media exceeds download limit")
                if response.getheader("Content-Encoding", "identity") != "identity":
                    raise ValueError("Unexpected compressed media transport")
                total = 0
                with destination.open("xb") as output:
                    created = True
                    while True:
                        check()
                        chunk = response.read1(128 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > max_bytes or time.monotonic() - started > deadline_seconds:
                            raise ValueError("Media download byte/time limit exceeded")
                        if progress:
                            progress(total)
                        output.write(chunk)
                if total == 0 or length and total != int(length):
                    raise ValueError("Empty or incomplete media download")
                return total
            finally:
                connection.close()
        raise ValueError("Too many media redirects")
    except BaseException:
        if created:
            destination.unlink(missing_ok=True)
        raise


class Storage:
    def __init__(self, db: Database, settings: Settings):
        self.db, self.settings = db, settings
        self.spool = settings.data_dir / "spool"
        self.spool.mkdir(parents=True, exist_ok=True)

    def check_free(self, extra=0):
        disk = shutil.disk_usage(self.spool)
        if disk.free - extra < self.settings.reserve_free_bytes or (disk.used + extra) / disk.total > self.settings.disk_high_water:
            raise ValueError("Storage reserve reached; new media work is paused")

    @contextlib.contextmanager
    def reserve(self, job_id: str, expected: int):
        if not re.fullmatch(r"[a-f0-9]{32}", job_id) or not 0 < expected <= self.settings.spool_limit_bytes:
            raise ValueError("Invalid storage reservation")
        with self.db.transaction() as conn:
            total = conn.execute("SELECT coalesce(sum(bytes),0) FROM reservations").fetchone()[0]
            if total + expected > self.settings.spool_limit_bytes:
                raise ValueError("Temporary storage is busy")
            self.check_free(total + expected)
            conn.execute("INSERT INTO reservations VALUES(?,?,?)", (job_id, expected, time.time() + 1800))
        directory = self.spool / job_id
        created = False
        try:
            directory.mkdir(exist_ok=False)
            created = True
            yield directory
        finally:
            if created and directory.is_dir() and not directory.is_symlink():
                shutil.rmtree(directory)
            self.db.execute("DELETE FROM reservations WHERE job_id=?", (job_id,))

    def get(self, key: str):
        row = self.db.one("SELECT value FROM cache WHERE key=? AND expires>?", (key, time.time()))
        if row:
            self.db.execute("UPDATE cache SET touched=? WHERE key=?", (time.time(), key))
            return json.loads(row["value"])
        return None

    def put(self, key: str, kind: str, value, ttl=30 * 86400):
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        size = len(encoded.encode())
        if size > min(16 * 1024**2, self.settings.cache_limit_bytes):
            raise ValueError("Cache item exceeds limit")
        self.check_free(size)
        now = time.time()
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM cache WHERE expires<?", (now,))
            conn.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?,?,?,?)", (key, kind, encoded, size, now, now + ttl))
            total = conn.execute("SELECT coalesce(sum(bytes),0) FROM cache").fetchone()[0]
            while total > self.settings.cache_limit_bytes:
                oldest = conn.execute("SELECT key,bytes FROM cache ORDER BY touched LIMIT 1").fetchone()
                conn.execute("DELETE FROM cache WHERE key=?", (oldest["key"],))
                total -= oldest["bytes"]

    def maintain(self):
        now = time.time()
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM nonces WHERE expires<?", (now,))
            conn.execute("DELETE FROM sessions WHERE expires<?", (now,))
            conn.execute("DELETE FROM rate_limits WHERE bucket<?", (int(now) // 60 - 10,))
            conn.execute("DELETE FROM cache WHERE expires<?", (now,))
            conn.execute("DELETE FROM cache_locks WHERE expires<?", (now,))
            conn.execute("DELETE FROM usage WHERE created<?", (now - 90 * 86400,))
            conn.execute("DELETE FROM jobs WHERE state IN ('done','failed','cancelled') AND updated<?", (now - 7 * 86400,))
            conn.execute("UPDATE jobs SET payload='{}' WHERE state IN ('done','failed','cancelled') AND payload!='{}'")
            total = conn.execute("SELECT coalesce(sum(length(cast(result AS BLOB))),0) FROM jobs WHERE state IN ('done','failed','cancelled')").fetchone()[0]
            while total > self.settings.job_history_limit_bytes:
                oldest = conn.execute("SELECT id,length(cast(result AS BLOB)) bytes FROM jobs WHERE state IN ('done','failed','cancelled') AND result IS NOT NULL ORDER BY updated LIMIT 1").fetchone()
                if not oldest:
                    break
                conn.execute("DELETE FROM jobs WHERE id=?", (oldest["id"],))
                total -= oldest["bytes"]
        for path in self.spool.iterdir():
            if path.is_symlink() or not path.is_dir() or not re.fullmatch(r"[a-f0-9]{32}", path.name):
                continue
            job = self.db.one("SELECT state,lease FROM jobs WHERE id=?", (path.name,))
            if path.stat().st_mtime < now - 1800 and (not job or job["state"] != "running" or (job["lease"] or 0) < now):
                shutil.rmtree(path)
                self.db.execute("DELETE FROM reservations WHERE job_id=?", (path.name,))
        with self.db.connect() as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.execute("PRAGMA incremental_vacuum(2048)")
