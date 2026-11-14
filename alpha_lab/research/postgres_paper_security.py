"""PostgreSQL ownership gate for research-only staging.

Only trusted server-side code may call provision; no HTTP input may choose an owner.
Ownership is checked on each request so revocation takes effect immediately.
"""
import re
from deployment.postgres_opaque_sessions import PostgresOpaqueSessions
from alpha_lab.research.paper_account_service import VerifiedPrincipal

SCHEMA = """
CREATE TABLE IF NOT EXISTS public.paper_ownership (
 owner_id text NOT NULL,
 account_key text NOT NULL,
 active boolean NOT NULL DEFAULT true,
 PRIMARY KEY(owner_id, account_key)
);
CREATE TABLE IF NOT EXISTS public.identity_rate_limit (
 identity_key text PRIMARY KEY,
 counter bigint NOT NULL DEFAULT 0
);
"""

class PostgresPaperOwnership:
    def __init__(self, connect):
        if not callable(connect):
            raise ValueError("trusted connection factory required")
        self._connect = connect

    @staticmethod
    def _account(account_key):
        if not isinstance(account_key, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", account_key):
            raise PermissionError("invalid account key")
        return account_key

    def provision(self, principal, account_key):
        if not isinstance(principal, VerifiedPrincipal):
            raise PermissionError("trusted verified principal required")
        owner = PostgresOpaqueSessions._owner(principal.subject, principal.issuer)
        account_key = self._account(account_key)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO public.paper_ownership(owner_id,account_key,active) VALUES (%s,%s,true) "
                    "ON CONFLICT(owner_id,account_key) DO NOTHING",
                    (owner, account_key))
        return owner

    def require_owner_id(self, owner, account_key):
        if not isinstance(owner, str) or not re.fullmatch(r"oidc_[a-f0-9]{64}", owner):
            raise PermissionError("invalid owner")
        account_key = self._account(account_key)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM public.paper_ownership WHERE owner_id=%s AND account_key=%s AND active=true",
                    (owner, account_key))
                allowed = cur.fetchone() is not None
        if not allowed:
            raise PermissionError("account access revoked or absent")
        return True

    def revoke_owner_id(self, owner, account_key):
        if not isinstance(owner, str) or not re.fullmatch(r"oidc_[a-f0-9]{64}", owner):
            raise PermissionError("invalid owner")
        account_key = self._account(account_key)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE public.paper_ownership SET active=false WHERE owner_id=%s AND account_key=%s",
                            (owner, account_key))
