"""Disposable PostgreSQL tenant-role provisioning example, never production.

Only run against a database explicitly named alpha_rls_test, with a
privileged disposable CI connection. Passwords supplied by the caller.
"""
import re
from psycopg import sql

def provision_disposable_tenant(admin, role, password, *, database_name):
    if database_name != "alpha_rls_test":
        raise PermissionError("disposable test database only")
    if not isinstance(role,str) or not re.fullmatch(r"alpha_tenant_[a-z0-9_]{1,80}",role):
        raise ValueError("invalid tenant role")
    if not isinstance(password,str) or len(password)<24:
        raise ValueError("strong synthetic test password required")
    with admin.cursor() as cur:
        cur.execute(sql.SQL("CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %s").format(sql.Identifier(role)),(password,))
        cur.execute(sql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(sql.Identifier(role)))
        cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
        cur.execute(sql.SQL("GRANT SELECT ON public.alpha_role_research TO {}").format(sql.Identifier(role)))
    # RLS policy must separately include this role; no broad PUBLIC policy.
