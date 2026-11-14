"""Synthetic tenant roles and research rows for loopback disposable tests."""
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from deployment.account_role_research_reader import AccountRoleResearchReader
from deployment.tenant_credential_broker import TenantCredentialBroker, tenant_login_role


class TenantResearchFixture:
    def __init__(self, admin, dsn, owner_ids):
        self.admin = admin
        self.dsn = dsn
        target = conninfo_to_dict(dsn)
        self.credentials = {
            owner: {"host": target["host"], "port": int(target["port"]),
                    "dbname": target["dbname"], "user": tenant_login_role(owner),
                    "password": "tenant-test-only"}
            for owner in owner_ids
        }

    def install(self):
        roles = [sql.Identifier(c["user"]) for c in self.credentials.values()]
        for role in roles:
            self.admin.execute(sql.SQL(
                "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOREPLICATION NOBYPASSRLS PASSWORD 'tenant-test-only'"
            ).format(role))
            self.admin.execute(sql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(role))
        self.admin.execute("""
            CREATE TABLE public.alpha_role_research (
                owner_role name NOT NULL, run_id text NOT NULL, evidence_sha256 text NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (owner_role, run_id)
            )
        """)
        for i, credential in enumerate(self.credentials.values()):
            self.admin.execute("INSERT INTO public.alpha_role_research(owner_role,run_id,evidence_sha256) VALUES (%s,%s,%s)",
                               (credential["user"], f"test-{i}", str(i) * 64))
        self.admin.execute("ALTER TABLE public.alpha_role_research ENABLE ROW LEVEL SECURITY")
        self.admin.execute("ALTER TABLE public.alpha_role_research FORCE ROW LEVEL SECURITY")
        self.admin.execute("REVOKE ALL ON public.alpha_role_research FROM PUBLIC")
        self.admin.execute(sql.SQL(
            "CREATE POLICY tenant_read ON public.alpha_role_research FOR SELECT TO {} "
            "USING (owner_role = SESSION_USER)"
        ).format(sql.SQL(", ").join(roles)))
        self.admin.execute(sql.SQL("GRANT SELECT ON public.alpha_role_research TO {}").format(
            sql.SQL(", ").join(roles)))

    def cleanup(self):
        self.admin.execute("DROP TABLE IF EXISTS public.alpha_role_research")
        for credential in self.credentials.values():
            self.admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(credential["user"])))

    def connect(self, **credentials):
        # The loopback CI PostgreSQL service does not have a trusted TLS certificate.
        return psycopg.connect(self.dsn, user=credentials["user"], password=credentials["password"],
                               sslmode="disable")

    def reader(self, connect=None):
        return AccountRoleResearchReader(TenantCredentialBroker(self.credentials.get, connect or self.connect))
