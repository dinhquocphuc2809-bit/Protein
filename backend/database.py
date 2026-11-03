from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets(
 id TEXT PRIMARY KEY, code_hash TEXT UNIQUE NOT NULL, label TEXT NOT NULL,
 duration INTEGER NOT NULL CHECK(duration>0), activated REAL, expires REAL,
 active INTEGER NOT NULL DEFAULT 1, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(
 id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL REFERENCES tickets(id),
 secret TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS nonces(
 session_id TEXT NOT NULL, nonce TEXT NOT NULL, expires REAL NOT NULL,
 PRIMARY KEY(session_id,nonce));
CREATE INDEX IF NOT EXISTS nonce_expiry ON nonces(expires);
CREATE TABLE IF NOT EXISTS rate_limits(
 scope TEXT NOT NULL, bucket INTEGER NOT NULL, count INTEGER NOT NULL,
 PRIMARY KEY(scope,bucket));
CREATE TABLE IF NOT EXISTS api_keys(
 id TEXT PRIMARY KEY, provider TEXT NOT NULL, label TEXT NOT NULL, fingerprint TEXT NOT NULL,
 encrypted TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'available', cooldown REAL NOT NULL DEFAULT 0,
 balance REAL, checked REAL, last_error TEXT, calls INTEGER NOT NULL DEFAULT 0,
 UNIQUE(provider,fingerprint));
CREATE TABLE IF NOT EXISTS config(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jobs(
 id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL REFERENCES tickets(id), kind TEXT NOT NULL,
 idem TEXT NOT NULL, request_hash TEXT NOT NULL, payload TEXT NOT NULL,
 state TEXT NOT NULL, stage TEXT NOT NULL, result TEXT, error TEXT,
 created REAL NOT NULL, updated REAL NOT NULL, lease REAL,
 UNIQUE(ticket_id,idem));
CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(state,created);
CREATE TABLE IF NOT EXISTS cache(
 key TEXT PRIMARY KEY, kind TEXT NOT NULL, value TEXT NOT NULL, bytes INTEGER NOT NULL,
 touched REAL NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS cache_locks(key TEXT PRIMARY KEY, owner TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS usage(
 id INTEGER PRIMARY KEY, ticket_id TEXT, job_id TEXT, provider TEXT NOT NULL,
 event TEXT NOT NULL, amount REAL NOT NULL DEFAULT 0, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS reservations(
 job_id TEXT PRIMARY KEY, bytes INTEGER NOT NULL CHECK(bytes>=0), expires REAL NOT NULL);
PRAGMA user_version=1;
"""


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as conn:
            if not conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
                conn.execute("PRAGMA auto_vacuum=INCREMENTAL")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)

    def connect(self):
        conn = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=15000")
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]
        conn.execute(f"PRAGMA max_page_count={6*1024**3//page_size}")
        conn.execute("PRAGMA journal_size_limit=67108864")
        return contextlib.closing(conn)

    @contextlib.contextmanager
    def transaction(self):
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def one(self, sql, args=()):
        with self.connect() as conn:
            row = conn.execute(sql, args).fetchone()
            return dict(row) if row is not None else None

    def all(self, sql, args=()):
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, args).fetchall()]

    def execute(self, sql, args=()):
        with self.transaction() as conn:
            return conn.execute(sql, args).rowcount
