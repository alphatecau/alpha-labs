"""Transaction-scoped PostgreSQL research reader.

The connection factory must return a dedicated connection as the restricted
reader role (no BYPASSRLS, no table ownership, no write grants). Never accept
SQL or owner identity from browser parameters.
"""
class TransactionScopedResearchReader:
    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    def list_runs(self, owner, limit=50):
        if not isinstance(owner, str) or not owner or type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("invalid owner or limit")
        with self.connection_factory() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("SELECT set_config('alpha_labs.owner_id', %s, true)", (owner,))
                    cur.execute(
                        "SELECT run_id, evidence_sha256, created_at FROM public.research_run_registry "
                        "ORDER BY created_at DESC, run_id DESC LIMIT %s", (limit,)
                    )
                    return [{"run_id": str(run_id), "evidence_sha256": sha,
                             "created_at": created_at.isoformat()} for run_id, sha, created_at in cur.fetchall()]

    def summary(self, owner):
        runs = self.list_runs(owner)
        return {"recent_run_count": len(runs), "count_scope": "latest_50",
                "performance": {"status": "unavailable", "reason": "no_verified_performance_view"},
                "provenance": {"status": "source_hashes_only", "records": runs}}
