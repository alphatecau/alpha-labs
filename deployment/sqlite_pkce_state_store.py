"""Atomic durable one-time Auth0 PKCE state store for single-instance staging.

Use private persistent storage. Multi-replica deployment requires shared
transactional storage; do not use in-memory state in production.
"""
import json
import sqlite3
import time


class SQLitePKCEStateStore:
    def __init__(self, path, clock=None):
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.execute("CREATE TABLE IF NOT EXISTS pkce_state (digest TEXT PRIMARY KEY, payload TEXT NOT NULL, expires INTEGER NOT NULL)")
        self.clock = clock or time.time

    def put(self, digest, record, ttl):
        if not isinstance(digest, str) or len(digest) != 64 or type(ttl) is not int or not 0 < ttl <= 300:
            raise ValueError("invalid PKCE state")
        self.db.execute("INSERT INTO pkce_state VALUES (?,?,?)",
                        (digest, json.dumps(record), int(self.clock()) + ttl))

    def consume(self, digest):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT payload,expires FROM pkce_state WHERE digest=?", (digest,)).fetchone()
            self.db.execute("DELETE FROM pkce_state WHERE digest=?", (digest,))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        if row is None or row[1] <= self.clock():
            return None
        return json.loads(row[0])

    def close(self):
        self.db.close()
