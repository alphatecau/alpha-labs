"""Disposable PostgreSQL 16 full BFF -> signed API -> RLS reader acceptance.

Requires ALPHA_TEST_PG_DSN pointing to a disposable superuser database.
Never run against staging or production.
"""
import json
import os
import tempfile
import unittest
from contextlib import contextmanager
import psycopg
from disposable_pg_guard import require_disposable_ci_database
from alpha_lab.research.oidc_durable_store import DurableOIDCStore
from alpha_lab.research.paper_ownership_registry import PaperOwnershipRegistry
from alpha_lab.research.paper_account_service import VerifiedPrincipal
from alpha_lab.research.postgres_paper_security import PostgresIdentityLimiter, SCHEMA
from deployment.bff_session_bridge import SessionOwnershipVerifier
from deployment.trusted_site_relay import TrustedSiteRelay
from deployment.research_dashboard_bff import ResearchDashboardBFF
from deployment.research_readonly_api import ResearchReadOnlyAPI
from deployment.transaction_scoped_research_reader import TransactionScopedResearchReader
from tenant_research_fixture import TenantResearchFixture


@unittest.skipUnless(os.environ.get("ALPHA_TEST_PG_DSN"), "isolated PostgreSQL required")
class FullChainPostgresTests(unittest.TestCase):
    def setUp(self):
        self.dsn = os.environ["ALPHA_TEST_PG_DSN"]
        require_disposable_ci_database(self.dsn)
        self.tmp = tempfile.TemporaryDirectory()
        self.sessions = DurableOIDCStore(self.tmp.name + "/sessions.sqlite")
        self.owners = PaperOwnershipRegistry(self.tmp.name + "/owners.sqlite")
        with psycopg.connect(self.dsn) as conn:
            conn.execute(SCHEMA)
        self.limiter = PostgresIdentityLimiter(lambda: psycopg.connect(self.dsn), limit=30, window=60)
        self.principals = [VerifiedPrincipal(subject=s, issuer="https://issuer.example/")
                           for s in ("alice", "bob")]
        verifier = SessionOwnershipVerifier(sessions=self.sessions, ownership=self.owners, limiter=self.limiter)
        self.cookies, owner_ids = [], []
        self.owner_ids = owner_ids
        for p in self.principals:
            self.owners.provision(p, "primary")
            self.cookies.append("__Host-alpha_session=" + self.sessions.create(p.subject, p.issuer))
            owner_ids.append(verifier(self.cookies[-1])["owner_id"])
        self.admin = psycopg.connect(self.dsn, autocommit=True)
        self.addCleanup(self.admin.close)
        self.admin.execute("CREATE ROLE alpha_chain_reader LOGIN PASSWORD 'test-only-reader' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION")
        self.admin.execute("CREATE TABLE public.research_run_registry (owner_id text NOT NULL, run_id text NOT NULL, evidence_sha256 text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(owner_id,run_id))")
        for index, owner in enumerate(owner_ids):
            self.admin.execute("INSERT INTO public.research_run_registry (owner_id,run_id,evidence_sha256) VALUES (%s,%s,%s)",
                               (owner, "test-" + str(index), str(index) * 64))
        self.admin.execute("ALTER TABLE public.research_run_registry ENABLE ROW LEVEL SECURITY")
        self.admin.execute("ALTER TABLE public.research_run_registry FORCE ROW LEVEL SECURITY")
        self.admin.execute("CREATE POLICY alpha_chain_owner ON public.research_run_registry FOR SELECT TO alpha_chain_reader USING (owner_id = NULLIF(current_setting('alpha_labs.owner_id',true),''))")
        self.admin.execute("REVOKE ALL ON public.research_run_registry FROM PUBLIC")
        self.admin.execute("GRANT USAGE ON SCHEMA public TO alpha_chain_reader")
        self.admin.execute("GRANT SELECT ON public.research_run_registry TO alpha_chain_reader")

        @contextmanager
        def restricted_connection():
            with psycopg.connect(self.dsn, user="alpha_chain_reader", password="test-only-reader") as conn:
                yield conn

        self.legacy_reader = TransactionScopedResearchReader(restricted_connection)
        tenant_fixture = TenantResearchFixture(self.admin, self.dsn, self.owner_ids)
        self.addCleanup(tenant_fixture.cleanup)
        tenant_fixture.install()
        secret = "test-only-" + "s" * 48
        api = ResearchReadOnlyAPI(reader=tenant_fixture.reader(), secret=secret)

        def backend(path, headers):
            response = {}
            raw = b"".join(api({"PATH_INFO": path, "REQUEST_METHOD": "GET",
                                "HTTP_AUTHORIZATION": headers["Authorization"]},
                               lambda status, hdr: response.update(status=status)))
            if not response["status"].startswith("200"):
                raise RuntimeError(response["status"])
            return json.loads(raw)

        self.app = ResearchDashboardBFF(relay=TrustedSiteRelay(verifier, backend, secret))

    def tearDown(self):
        if hasattr(self, "admin"):
            self.admin.execute("DROP TABLE public.identity_rate_limit, public.paper_ownership")
            self.admin.execute("DROP TABLE IF EXISTS public.research_run_registry")
            # Disposable test database only: remove grants before dropping role.
            self.admin.execute("DROP OWNED BY alpha_chain_reader")
            self.admin.execute("DROP ROLE IF EXISTS alpha_chain_reader")
        self.sessions.close()
        self.owners.close()
        self.tmp.cleanup()

    def request(self, cookie="", path="/api/research/runs", method="GET"):
        response = {}
        raw = b"".join(self.app({"PATH_INFO": path, "REQUEST_METHOD": method,
                                  "wsgi.url_scheme": "https", "QUERY_STRING": "",
                                  "HTTP_COOKIE": cookie},
                                 lambda status, headers: response.update(status=status)))
        return response["status"], json.loads(raw)

    def test_two_user_isolation_missing_context_and_write_denial(self):
        a_status, a = self.request(self.cookies[0])
        b_status, b = self.request(self.cookies[1])
        self.assertTrue(a_status.startswith("200"), a)
        self.assertTrue(b_status.startswith("200"), b)
        self.assertEqual([r["run_id"] for r in a["data"]], ["test-0"])
        self.assertEqual([r["run_id"] for r in b["data"]], ["test-1"])
        self.assertTrue(self.request()[0].startswith("401"))
        self.assertTrue(self.request(self.cookies[0], method="POST")[0].startswith("405"))
        with psycopg.connect(self.dsn, user="alpha_chain_reader", password="test-only-reader") as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM public.research_run_registry").fetchone()[0], 0)
            self.assertFalse(conn.execute("SELECT has_table_privilege(current_user, 'public.research_run_registry', 'INSERT')").fetchone()[0])
        self.owners.revoke(self.principals[0], "primary")
        self.assertTrue(self.request(self.cookies[0])[0].startswith("401"))

    def test_reused_connection_resets_tenant_context_on_commit_and_rollback(self):
        with self.legacy_reader.connection_factory() as conn:
            conn.autocommit = True
            @contextmanager
            def pooled_connection():
                yield conn
            pooled = TransactionScopedResearchReader(pooled_connection)
            for index in (0, 1, 0, 1):
                rows = pooled.list_runs(self.owner_ids[index])
                self.assertEqual([r["run_id"] for r in rows], ["test-" + str(index)])
                self.assertEqual(conn.execute("SELECT count(*) FROM public.research_run_registry").fetchone()[0], 0)
            with self.assertRaisesRegex(RuntimeError, "synthetic rollback"):
                with conn.transaction():
                    conn.execute("SELECT set_config('alpha_labs.owner_id',%s,true)", (self.owner_ids[0],))
                    raise RuntimeError("synthetic rollback")
            self.assertEqual(conn.execute("SELECT count(*) FROM public.research_run_registry").fetchone()[0], 0)

    def test_shared_reader_guc_is_not_independent_tenant_authority(self):
        # Preserve the historical exploit and prove this adapter cannot back the signed API.
        with self.legacy_reader.connection_factory() as conn:
            conn.execute("SELECT set_config('alpha_labs.owner_id',%s,true)", (self.owner_ids[1],))
            self.assertEqual(conn.execute("SELECT run_id FROM public.research_run_registry").fetchall(), [("test-1",)])
        with self.assertRaisesRegex(ValueError, "tenant-role research reader required"):
            ResearchReadOnlyAPI(reader=self.legacy_reader)


if __name__ == "__main__":
    unittest.main()
