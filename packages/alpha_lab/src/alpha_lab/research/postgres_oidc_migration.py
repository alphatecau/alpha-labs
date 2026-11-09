"""Explicit PostgreSQL OIDC schema migration for isolated research staging."""
from alpha_lab.research.oidc_postgres_store import SCHEMA

MIGRATION_ID = "20261109_oidc_sessions_v1"


def apply_oidc_schema(connect):
    if not callable(connect):
        raise ValueError("Explicit PostgreSQL connection required")
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS alpha_schema_migrations ("
                        "id TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)")
            cur.execute(SCHEMA)
            cur.execute("INSERT INTO alpha_schema_migrations(id) VALUES(%s) "
                        "ON CONFLICT(id) DO NOTHING", (MIGRATION_ID,))


def verify_oidc_schema(connect):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM alpha_schema_migrations WHERE id=%s", (MIGRATION_ID,))
            if cur.fetchone() != (MIGRATION_ID,):
                raise PermissionError("OIDC schema migration missing")
            cur.execute("SELECT to_regclass('public.oidc_pending'), "
                        "to_regclass('public.oidc_sessions')")
            row = cur.fetchone()
            if not row or not all(row):
                raise PermissionError("OIDC session tables missing")
    return True
