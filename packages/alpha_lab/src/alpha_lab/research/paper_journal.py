"""Research-only durable append-only journal; not a multi-user trading database."""
import json
import os
import sqlite3
from hashlib import sha256

class PaperJournal:
    def __init__(self, path):
        if path == ":memory:":
            raise ValueError("persistent journal path required")
        self.connection = sqlite3.connect(path)
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.execute("CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, previous_hash TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL)")
        self.connection.commit()

    def verify(self):
        previous = "0" * 64
        expected_seq = 1
        for seq, prior, payload, digest in self.connection.execute(
                "SELECT seq,previous_hash,payload,digest FROM events ORDER BY seq"):
            if seq != expected_seq:
                raise ValueError("journal sequence gap: HALT")
            expected_seq += 1
            expected = sha256((previous + payload).encode()).hexdigest()
            if prior != previous or digest != expected:
                raise ValueError("journal integrity failure: HALT")
            previous = digest
        return previous

    def append(self, event, *, expected_seq=None, expected_head=None):
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            previous = self.verify()
            if expected_seq is not None:
                current_seq = self.connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                if current_seq != expected_seq or previous != expected_head:
                    raise ValueError("stale journal state: HALT")
            order_id = event.get("order_id")
            if order_id is not None:
                for (existing_payload,) in self.connection.execute("SELECT payload FROM events"):
                    if json.loads(existing_payload).get("order_id") == order_id:
                        raise ValueError("duplicate simulated order ID: HALT")
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
