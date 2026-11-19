"""Read-only Android auditor preflight. Does not ask for or print secrets.

Run after securely setting LEVEL3_AUDITOR_READONLY_DSN on the device.
No checkpoint is written; no database mutation is performed.
"""
import os

EXPECTED_ROLE = "level3_auditor_login"


def main():
    dsn = os.environ.get("LEVEL3_AUDITOR_READONLY_DSN")
    if not dsn:
        raise SystemExit("BLOCKED: read-only Neon DSN not configured")
    import psycopg
    with psycopg.connect(dsn, autocommit=True, connect_timeout=10) as conn:
        conn.execute("SET default_transaction_read_only = on")
        role = conn.execute("SELECT current_user").fetchone()[0]
        if role != EXPECTED_ROLE:
            raise SystemExit("BLOCKED: wrong Neon database role")
        permissions = conn.execute(
            "SELECT has_table_privilege(current_user,'level3_custody.audit_event','SELECT'),"
            "has_table_privilege(current_user,'level3_custody.audit_event','INSERT'),"
            "has_table_privilege(current_user,'level3_custody.audit_event','UPDATE'),"
            "has_table_privilege(current_user,'level3_custody.audit_event','DELETE'),"
            "has_table_privilege(current_user,'level3_custody.audit_event','TRUNCATE')"
        ).fetchone()
        if tuple(permissions) != (True, False, False, False, False):
            raise SystemExit("BLOCKED: unsafe auditor audit-event privileges")
        from tools.level3_staging.postgres_custody import verify_audit_chain
        head = verify_audit_chain(conn)
        print("PASS: dedicated Neon auditor role and read-only audit privileges")
        print("PASS: audit-chain integrity verified")
        print("Audit event count:", head["count"])
        print("Last sequence:", head["last_sequence"])
        print("Head hash:", head["head_hash"])
        if head["count"] == 0:
            print("BLOCKED: no real audit event exists to checkpoint")
        else:
            print("READY: nonempty audit chain available for signed checkpoint")
        print("No database or Drive writes performed")


if __name__ == "__main__":
    main()
