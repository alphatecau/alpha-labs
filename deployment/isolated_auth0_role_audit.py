"""Read-only audit of the isolated Auth0 PostgreSQL runtime roles.

This module deliberately performs no DDL, grants, provisioning or mutations.
Run it using a separate audit connection to a disposable staging database.
"""
import re


_REQUIRED = {
    "oauth": ("public.alpha_oauth_transactions", {"SELECT", "INSERT", "DELETE"}),
    "session": ("public.alpha_oidc_sessions", {"SELECT", "INSERT", "DELETE"}),
    "ownership": ("public.paper_ownership", {"SELECT"}),
}


def audit_runtime_roles(connect, *, oauth_role, session_role, ownership_role):
    roles = {"oauth": oauth_role, "session": session_role, "ownership": ownership_role}
    if not callable(connect):
        raise ValueError("audit connection required")
    if any(not isinstance(v, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", v)
           for v in roles.values()) or len(set(roles.values())) != 3:
        raise ValueError("three distinct restricted role names required")
    results = {}
    with connect() as conn:
        with conn.cursor() as cur:
            for purpose, role in roles.items():
                table, expected = _REQUIRED[purpose]
                cur.execute(
                    "SELECT rolcanlogin, rolsuper, rolbypassrls, rolcreaterole, "
                    "rolcreatedb, rolreplication FROM pg_catalog.pg_roles WHERE rolname=%s",
                    (role,))
                flags = cur.fetchone()
                if flags != (True, False, False, False, False, False):
                    raise PermissionError("unsafe or absent runtime role: " + purpose)
                cur.execute("SELECT pg_catalog.to_regclass(%s)", (table,))
                if cur.fetchone()[0] is None:
                    raise PermissionError("missing isolated schema: " + purpose)
                cur.execute(
                    "SELECT c.relowner = r.oid FROM pg_catalog.pg_class c "
                    "JOIN pg_catalog.pg_roles r ON r.rolname=%s "
                    "WHERE c.oid=pg_catalog.to_regclass(%s)", (role, table))
                owner = cur.fetchone()
                if owner is None or owner[0]:
                    raise PermissionError("runtime role owns protected table: " + purpose)
                cur.execute(
                    "SELECT pg_catalog.has_schema_privilege(%s,'public','CREATE')",
                    (role,))
                if cur.fetchone() != (False,):
                    raise PermissionError("runtime role may create public objects")
                allowed = {}
                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE",
                                  "TRUNCATE", "REFERENCES", "TRIGGER"):
                    cur.execute(
                        "SELECT pg_catalog.has_table_privilege(%s,%s,%s)",
                        (role, table, privilege))
                    allowed[privilege] = cur.fetchone() == (True,)
                if {k for k, v in allowed.items() if v} != expected:
                    raise PermissionError("unexpected table grants: " + purpose)
                results[purpose] = {"role": role, "table": table, "grants": sorted(expected)}
    return results
