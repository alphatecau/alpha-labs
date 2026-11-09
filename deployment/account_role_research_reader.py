"""Research-only tenant-specific PostgreSQL reader.

Credential resolver is a trusted server-side mapping of VERIFIED owner IDs to
distinct restricted database connections. Never accept a DSN, role, SQL, or
account selection from an HTTP request. No fallback to shared superuser.
"""
import re


class AccountRoleResearchReader:
    def __init__(self, verified_connection_factory):
        if not callable(verified_connection_factory):
            raise ValueError("trusted account connection factory required")
        self._connect = verified_connection_factory

    def list_runs(self, owner, limit=50):
        if not isinstance(owner, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", owner):
            raise ValueError("invalid verified owner")
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("invalid limit")
        # Factory must fail closed for unprovisioned owners, and use a distinct
        # PostgreSQL LOGIN role without membership in other tenant roles.
        with self._connect(owner) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT run_id, evidence_sha256, created_at "
                    "FROM public.alpha_role_research "
                    "ORDER BY created_at DESC, run_id DESC LIMIT %s", (limit,)
                )
                return [{"run_id": str(run_id), "evidence_sha256": sha,
                         "created_at": created_at.isoformat()} for run_id, sha, created_at in cur.fetchall()]

    def summary(self, owner):
        runs = self.list_runs(owner)
        return {"recent_run_count": len(runs), "count_scope": "latest_50",
                "performance": {"status": "unavailable", "reason": "no_verified_performance_view"},
                "provenance": {"status": "source_hashes_only", "records": runs}}
