"""Fail-closed research-only shared-file SQLite rate limiter.

Not appropriate for multi-host deployment; migrate to shared PostgreSQL
before staging. Counters are enforced transactionally per identity.
"""
import hashlib
import sqlite3
import time


class SQLiteIdentityLimiter:
    def __init__(self, path, *, limit=30, window=60, clock=None):
        if not isinstance(path, str) or not path or not isinstance(limit, int) or limit < 1 or not isinstance(window, int) or window < 1:
            raise ValueError("Explicit valid rate limit configuration required")
        self.db = sqlite3.connect(path, timeout=5, isolation_level=None)
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("CREATE TABLE IF NOT EXISTS identity_rate_limit (identity TEXT PRIMARY KEY, bucket INTEGER NOT NULL, count INTEGER NOT NULL)")
        self.limit, self.window, self.clock = limit, window, clock or time.time

    def allow(self, issuer, subject):
        if not isinstance(issuer, str) or not issuer.startswith("https://") or not isinstance(subject, str) or not subject:
            raise PermissionError("Verified identity required")
        key = hashlib.sha256((issuer + "\0" + subject).encode()).hexdigest()
        bucket = int(self.clock()) // self.window
        try:
            self.db.execute("BEGIN IMMEDIATE")
            self.db.execute("INSERT INTO identity_rate_limit(identity,bucket,count) VALUES(?,?,1) "
                            "ON CONFLICT(identity) DO UPDATE SET "
                            "count=CASE WHEN bucket=excluded.bucket THEN count+1 ELSE 1 END, "
                            "bucket=excluded.bucket", (key, bucket))
            count = self.db.execute("SELECT count FROM identity_rate_limit WHERE identity=?", (key,)).fetchone()[0]
            self.db.execute("COMMIT")
        except Exception:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise PermissionError("Rate limit unavailable")
        if count > self.limit:
            raise PermissionError("Rate limit exceeded")
        return True

    def close(self):
        self.db.close()
