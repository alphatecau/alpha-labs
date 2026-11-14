"""Fail-closed tenant credential broker for read-only PostgreSQL connections.

The mapping is supplied by a trusted secret provider, not request headers.
Provisioning, rotation and external vault access are intentionally separate.
"""
import re
from contextlib import contextmanager


class TenantCredentialBroker:
    def __init__(self, lookup_secret, connect):
        if not callable(lookup_secret) or not callable(connect):
            raise ValueError("trusted secret provider and connector required")
        self._lookup, self._connect = lookup_secret, connect

    @contextmanager
    def __call__(self, verified_owner):
        if not isinstance(verified_owner, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", verified_owner):
            raise PermissionError("invalid verified account")
        credentials = self._lookup(verified_owner)
        if not isinstance(credentials, dict) or set(credentials) != {"host", "port", "dbname", "user", "password"}:
            raise PermissionError("account not provisioned")
        if (not all(isinstance(credentials[k], str) and credentials[k] for k in ("host","dbname","user","password"))
                or type(credentials["port"]) is not int or not 1 <= credentials["port"] <= 65535
                or not re.fullmatch(r"alpha_tenant_[a-z0-9_]{1,80}", credentials["user"])):
            raise PermissionError("invalid tenant credential configuration")
        # No dynamic SQL, no superuser fallback, no caller-provided DSN.
        with self._connect(host=credentials["host"], port=credentials["port"],
                           dbname=credentials["dbname"], user=credentials["user"],
                           password=credentials["password"], sslmode="verify-full",
                           connect_timeout=5) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_user, rolsuper, rolbypassrls, rolcreaterole FROM pg_roles WHERE rolname=current_user")
                row = cursor.fetchone()
                if not row or row[0] != credentials["user"] or any(row[1:]):
                    raise PermissionError("unsafe database identity")
                cursor.execute("SHOW transaction_read_only")
                if cursor.fetchone()[0] != "on":
                    # Privileges remain SELECT-only even when server is not read-only;
                    # require server-enforced read-only default for defence in depth.
                    raise PermissionError("read-only database session required")
            yield connection
