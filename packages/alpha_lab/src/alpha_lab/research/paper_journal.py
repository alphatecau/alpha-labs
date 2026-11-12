"""Research-only durable append-only journal; not a multi-user trading database."""
import json
import fcntl
import os
import sqlite3
from hashlib import sha256

class PaperJournal:
    def __init__(self, path):
        if path == ":memory:":
            raise ValueError("persistent journal path required")
        # POSIX-only exclusive single-writer lock, acquired before journal replay.
        self._lock_file = open(str(path) + ".writer.lock", "a+b")
        try:
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError) as exc:
            self._lock_file.close()
            raise PermissionError("HALT: paper journal already has a writer") from exc
        try:
            self.connection = sqlite3.connect(path)
        except Exception:
            self._lock_file.close()
            raise
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.execute("CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, previous_hash TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL)")
        self.connection.commit()

    def verify(self):
        previous = "0" * 64
        for seq, prior, payload, digest in self.connection.execute(
                "SELECT seq,previous_hash,payload,digest FROM events ORDER BY seq"):
            expected = sha256((previous + payload).encode()).hexdigest()
            if prior != previous or digest != expected:
                raise ValueError("journal integrity failure: HALT")
            previous = digest
        return previous

    def append(self, event):
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            previous = self.verify()
            payload = json.dumps(event, sort_keys=True, separators=(",", ":"), allow_nan=False)
            digest = sha256((previous + payload).encode()).hexdigest()
            self.connection.execute("INSERT INTO events(previous_hash,payload,digest) VALUES(?,?,?)",
                                    (previous, payload, digest))
            self.connection.commit()
            return digest
        except Exception:
            self.connection.rollback()
            raise

    def close(self):
        self.connection.close()
        self._lock_file.close()
