"""Explicitly authorised staging-only custody transaction through audited APIs.

Requires a dedicated broker DSN and an explicit opt-in. Never touches live trading.
This is a synthetic STAGING custody event, not a real customer approval.
"""
import hashlib
import os
import secrets
import uuid


def main():
    if os.environ.get("LEVEL3_STAGING_CUSTODY_SMOKE") != "I_AUTHORISE_SYNTHETIC_STAGING_EVENT":
        raise SystemExit("BLOCKED: explicit synthetic staging authorisation required")
    dsn = os.environ.get("LEVEL3_STAGING_BROKER_DSN")
    if not dsn:
        raise SystemExit("BLOCKED: dedicated staging broker DSN required")
    import psycopg
    from tools.level3_staging.postgres_custody import (
        claim_with_audit, complete_with_audit, verify_audit_chain
    )
    nonce = secrets.token_hex(32)
    remote_nonce = secrets.token_hex(32)
    digest = hashlib.sha256(("level3-staging-custody-smoke-v1:" + nonce).encode()).hexdigest()
    path = "tests/level3-staging/synthetic_custody_smoke.txt"
    with psycopg.connect(dsn, autocommit=True, connect_timeout=10) as conn:
        conn.execute("SET statement_timeout = '15s'")
        db = conn.execute("SELECT current_database()").fetchone()[0]
        if db != "level3custody":
            raise SystemExit("BLOCKED: expected isolated level3custody database")
        role = conn.execute("SELECT current_user").fetchone()[0]
        if role != "level3_broker_login":
            raise SystemExit("BLOCKED: expected dedicated level3_broker_login role")
        with conn.transaction():
            claimed = claim_with_audit(conn, remote_nonce, nonce, path, digest, str(uuid.uuid4()))
            completed = complete_with_audit(conn, nonce, path, digest, str(uuid.uuid4()))
        head = verify_audit_chain(conn)
    if claimed["state"] != "claimed" or completed["state"] != "complete" or head["count"] < 2:
        raise RuntimeError("FAIL: audited staging custody transaction incomplete")
    print("PASS: staging custody claim and completion audited atomically")
    print("Audit event count:", head["count"])
    print("Audit head hash:", head["head_hash"])
    print("Synthetic staging event only; no trading or production approval")


if __name__ == "__main__":
    main()
