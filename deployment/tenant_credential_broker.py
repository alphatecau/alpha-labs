"""Fail-closed tenant credential broker for read-only PostgreSQL connections.

The mapping is supplied by a trusted secret provider, not request headers.
Provisioning, rotation and external vault access are intentionally separate.
"""
import re
from contextlib import contextmanager


def tenant_login_role(owner):
    """Bind the verified OIDC owner to a PostgreSQL name (at most 63 bytes)."""
    if not isinstance(owner, str) or not re.fullmatch(r"oidc_[0-9a-f]{64}", owner):
        raise PermissionError("invalid verified account")
    return "alpha_tenant_" + owner[5:55]


_LOGIN_CHECK = """
SELECT session_user = %s AND current_user = session_user
       AND rolcanlogin AND NOT (rolsuper OR rolbypassrls OR rolcreaterole
                                OR rolcreatedb OR rolreplication)
       AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members WHERE member = r.oid)
       AND EXISTS (SELECT 1 FROM pg_catalog.pg_stat_activity
                   WHERE pid = pg_catalog.pg_backend_pid() AND usesysid = r.oid)
FROM pg_catalog.pg_roles AS r WHERE rolname = session_user
"""

_TABLE_CHECK = """
SELECT c.relkind = 'r' AND c.relrowsecurity AND c.relforcerowsecurity
       AND c.relowner <> r.oid AND pg_catalog.row_security_active(c.oid)
       AND NOT pg_catalog.has_schema_privilege(r.oid, 'public', 'CREATE')
       AND pg_catalog.has_table_privilege(r.oid, c.oid, 'SELECT')
       AND NOT pg_catalog.has_table_privilege(r.oid, c.oid, 'DELETE,TRUNCATE,TRIGGER')
       AND NOT pg_catalog.has_any_column_privilege(
           r.oid, c.oid, 'INSERT,UPDATE,REFERENCES,SELECT WITH GRANT OPTION')
       AND NOT COALESCE(pg_catalog.has_any_column_privilege(
           r.oid, pg_catalog.to_regclass('public.research_run_registry')::oid, 'SELECT'), false)
       AND (SELECT count(*) = 1 AND count(*) FILTER (
                    WHERE p.polcmd = 'r' AND p.polpermissive AND r.oid = ANY(p.polroles)
                      AND pg_catalog.pg_get_expr(p.polqual, p.polrelid) = '(owner_role = SESSION_USER)'
                ) = 1
            FROM pg_catalog.pg_policy AS p WHERE p.polrelid = c.oid)
FROM pg_catalog.pg_class AS c, pg_catalog.pg_roles AS r
WHERE c.oid = pg_catalog.to_regclass('public.alpha_role_research') AND r.rolname = session_user
"""


class TenantCredentialBroker:
    def __init__(self, lookup_secret, connect):
        if not callable(lookup_secret) or not callable(connect):
            raise ValueError("trusted secret provider and connector required")
        self._lookup, self._connect = lookup_secret, connect

    @contextmanager
    def __call__(self, verified_owner):
        expected_role = tenant_login_role(verified_owner)
        credentials = self._lookup(verified_owner)
        if not isinstance(credentials, dict) or set(credentials) != {"host", "port", "dbname", "user", "password"}:
            raise PermissionError("account not provisioned")
        if (not all(isinstance(credentials[k], str) and credentials[k] for k in ("host","dbname","user","password"))
                or type(credentials["port"]) is not int or not 1 <= credentials["port"] <= 65535
                or credentials["user"] != expected_role):
            raise PermissionError("invalid tenant credential configuration")
        # No dynamic SQL, no superuser fallback, no caller-provided DSN.
        with self._connect(host=credentials["host"], port=credentials["port"],
                           dbname=credentials["dbname"], user=credentials["user"],
                           password=credentials["password"], sslmode="verify-full",
                           connect_timeout=5) as connection:
            # Keep identity, policy checks and reads on the same transaction and
            # physical connection, including with a transaction-mode pooler.
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(_LOGIN_CHECK, (expected_role,))
                    if cursor.fetchone() != (True,):
                        raise PermissionError("unsafe database identity")
                    cursor.execute("SHOW transaction_read_only")
                    if cursor.fetchone() != ("on",):
                        raise PermissionError("read-only database session required")
                    cursor.execute(_TABLE_CHECK)
                    if cursor.fetchone() != (True,):
                        raise PermissionError("unsafe tenant table policy or grants")
                yield connection
