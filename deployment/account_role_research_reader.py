"""Research-only tenant-specific PostgreSQL reader.

Credential resolver is a trusted server-side mapping of VERIFIED owner IDs to
distinct restricted database connections. Never accept a DSN, role, SQL, or
account selection from an HTTP request. No fallback to shared superuser.
"""
from deployment.tenant_credential_broker import TenantCredentialBroker


class AccountRoleResearchReader:
    def __init__(self, broker):
        if not isinstance(broker, TenantCredentialBroker):
            raise ValueError("tenant credential broker required")
        self._connect = broker

    def list_runs(self, owner, limit=50):
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("invalid limit")
        # Factory must fail closed for unprovisioned owners, and use a distinct
        # PostgreSQL LOGIN role without membership in other tenant roles.
        with self._connect(owner) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT run_id, evidence_sha256, created_at "
                    "FROM ONLY public.alpha_role_research WHERE owner_role = session_user "
                    "ORDER BY created_at DESC, run_id DESC LIMIT %s", (limit,)
                )
                return [{"run_id": str(run_id), "evidence_sha256": sha,
                         "created_at": created_at.isoformat()} for run_id, sha, created_at in cur.fetchall()]

    def summary(self, owner):
        runs = self.list_runs(owner)
        return {"recent_run_count": len(runs), "count_scope": "latest_50",
                "performance": {"status": "unavailable", "reason": "no_verified_performance_view"},
                "provenance": {"status": "source_hashes_only", "records": runs}}
