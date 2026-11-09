"""Read-only PostgreSQL adapter; expects pre-existing approved, owner-scoped view.

Never creates schema or falls back to synthetic values.
"""
class PostgresResearchReader:
    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    def list_runs(self, owner, limit=50):
        if not isinstance(owner, str) or not owner or not isinstance(limit, int) or not 1 <= limit <= 50:
            raise ValueError("invalid query")
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT run_id, evidence_sha256, created_at
                    FROM research_run_registry
                    WHERE owner_id = %s
                    ORDER BY created_at DESC, run_id DESC
                    LIMIT %s
                """, (owner, limit))
                return [{"run_id": str(run_id), "evidence_sha256": sha,
                         "created_at": created_at.isoformat()} for run_id, sha, created_at in cur.fetchall()]

    def summary(self, owner):
        runs = self.list_runs(owner, limit=50)
        return {"recent_run_count": len(runs), "count_scope": "latest_50",
                "performance": {"status": "unavailable", "reason": "no_verified_performance_view"},
                "provenance": {"status": "source_hashes_only", "records": runs}}
