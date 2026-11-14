"""Durable single-use Auth0 state store; isolated PostgreSQL staging only.

Install schema with a migration role; runtime requires narrow SELECT/INSERT/DELETE.
"""
import hashlib
import json

SCHEMA = """
CREATE TABLE IF NOT EXISTS public.alpha_oauth_transactions (
 state_hash text PRIMARY KEY,
 payload jsonb NOT NULL,
 expires_at timestamptz NOT NULL
);
"""


class PostgresOAuthStateStore:
    def __init__(self, connect):
        if not callable(connect):
            raise ValueError("trusted connection factory required")
        self.connect = connect

    @staticmethod
    def _hash(state):
        if not isinstance(state, str) or not 32 <= len(state) <= 256:
            raise PermissionError("invalid state")
        return hashlib.sha256(state.encode()).hexdigest()

    def put(self, state, payload):
        digest = self._hash(state)
        if not isinstance(payload, dict) or not isinstance(payload.get("expires"), int):
            raise ValueError("invalid state payload")
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO public.alpha_oauth_transactions(state_hash,payload,expires_at) "
                    "VALUES (%s,%s,to_timestamp(%s))",
                    (digest, json.dumps(payload), payload["expires"]),
                )

    def consume(self, state):
        digest = self._hash(state)
        with self.connect() as conn:
            with conn.cursor() as cur:
                # A single atomic statement prevents callback replay and concurrent reuse.
                cur.execute(
                    "DELETE FROM public.alpha_oauth_transactions "
                    "WHERE state_hash=%s AND expires_at>now() RETURNING payload",
                    (digest,),
                )
                row = cur.fetchone()
        if row is None:
            raise PermissionError("expired or replayed OAuth state")
        return row[0] if isinstance(row[0], dict) else json.loads(row[0])
