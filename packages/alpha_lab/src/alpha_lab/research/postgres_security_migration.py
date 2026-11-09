"""Idempotent, reviewable paper-security schema migration; never runs on import.

Operator must explicitly call apply_schema on an authorised isolated database.
Production credentials and automatic migrations are intentionally unsupported.
"""
from alpha_lab.research.postgres_paper_security import SCHEMA

MIGRATION_ID = "20261109_paper_security_v1"


def apply_schema(connect):
    if not callable(connect):
        raise ValueError("Explicit database connection factory required")
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS alpha_schema_migrations ("
                        "id TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)")
            cur.execute(SCHEMA)
            cur.execute("INSERT INTO alpha_schema_migrations(id) VALUES(%s) "
                        "ON CONFLICT(id) DO NOTHING", (MIGRATION_ID,))


def verify_schema(connect):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM alpha_schema_migrations WHERE id=%s", (MIGRATION_ID,))
            if cur.fetchone() != (MIGRATION_ID,):
                raise PermissionError("Required migration absent")
            cur.execute("SELECT to_regclass('public.paper_ownership'), "
                        "to_regclass('public.identity_rate_limit')")
            row = cur.fetchone()
            if not row or not all(row):
                raise PermissionError("Required tables absent")
    return True
