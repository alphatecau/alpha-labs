"""Atomic PostgreSQL PKCE state store for multi-process staging.

Requires a separately migrated table and restricted DB role. No auto-DDL.
"""
import json
import re
import time

SCHEMA = """CREATE TABLE alpha_oauth_state (
 digest char(64) PRIMARY KEY,
 payload jsonb NOT NULL,
 expires_at timestamptz NOT NULL
);"""

class PostgresPKCEStateStore:
    def __init__(self, connect, *, clock=None):
        if not callable(connect):
            raise ValueError("trusted connection factory required")
        self.connect = connect
        self.clock = clock or time.time

    def put(self, digest, record, ttl):
        if not isinstance(digest,str) or not re.fullmatch(r"[0-9a-f]{64}",digest) or type(ttl) is not int or not 1 <= ttl <= 300:
            raise ValueError("invalid state")
        if not isinstance(record,dict) or set(record) != {"nonce","verifier","created_at"}:
            raise ValueError("invalid state payload")
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO alpha_oauth_state(digest,payload,expires_at) VALUES (%s,%s,to_timestamp(%s))",
                            (digest,json.dumps(record),self.clock()+ttl))

    def consume(self,digest):
        if not isinstance(digest,str) or not re.fullmatch(r"[0-9a-f]{64}",digest):
            return None
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM alpha_oauth_state WHERE digest=%s RETURNING payload,expires_at>to_timestamp(%s)",
                            (digest,self.clock()))
                row=cur.fetchone()
        if not row or not row[1]:
            return None
        payload=row[0]
        if isinstance(payload,str):
            payload=json.loads(payload)
        return payload if isinstance(payload,dict) else None
