"""Research-only PostgreSQL account ownership and per-identity rate limit.

Requires caller-managed migrations and an injected psycopg-compatible connection
factory. No connection strings, migrations or deployment are performed here.
"""
import hashlib
import re

from alpha_lab.research.paper_account_service import VerifiedPrincipal


SCHEMA = """
CREATE TABLE IF NOT EXISTS paper_ownership (
    owner_digest TEXT NOT NULL,
    account TEXT NOT NULL,
    active BOOLEAN NOT NULL,
    PRIMARY KEY(owner_digest, account)
);
CREATE TABLE IF NOT EXISTS identity_rate_limit (
    identity TEXT PRIMARY KEY,
    bucket BIGINT NOT NULL,
    count BIGINT NOT NULL CHECK (count >= 0)
);
"""


def _identity(issuer, subject):
    if (not isinstance(issuer, str) or not issuer.startswith("https://")
            or len(issuer) > 255 or not isinstance(subject, str)
            or not re.fullmatch(r"[A-Za-z0-9_|:-]{1,128}", subject)):
        raise PermissionError("Invalid verified identity")
    return hashlib.sha256((issuer + "\0" + subject).encode()).hexdigest()


class PostgresPaperOwnership:
    def __init__(self, connect):
        if not callable(connect):
            raise ValueError("Connection factory required")
        self._connect = connect

    def _key(self, principal, account):
        if not isinstance(principal, VerifiedPrincipal) or not isinstance(account, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", account):
            raise PermissionError("Verified identity and account required")
        return _identity(principal.issuer, principal.subject), account

    def provision(self, principal, account):
        key = self._key(principal, account)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO paper_ownership(owner_digest,account,active) VALUES(%s,%s,TRUE) "
                            "ON CONFLICT(owner_digest,account) DO UPDATE SET active=TRUE", key)

    def revoke(self, principal, account):
        key = self._key(principal, account)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE paper_ownership SET active=FALSE WHERE owner_digest=%s AND account=%s", key)

    def require(self, principal, account):
        key = self._key(principal, account)
        return self._require_key(key)

    def require_owner_id(self, owner_id, account):
        """Trusted session adapter only; never accept an owner from a browser."""
        if (not isinstance(owner_id, str) or not re.fullmatch(r"oidc_[a-f0-9]{64}", owner_id)
                or not isinstance(account, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", account)):
            raise PermissionError("Verified owner ID and account required")
        return self._require_key((owner_id[5:], account))

    def _require_key(self, key):
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT active FROM paper_ownership WHERE owner_digest=%s AND account=%s", key)
                row = cur.fetchone()
        if row is None or row[0] is not True:
            raise PermissionError("Account not provisioned")
        return True


class RateLimitExceeded(PermissionError):
    """The shared bucket has no remaining allowance."""


class RateLimitUnavailable(PermissionError):
    """The shared store could not confirm an admission."""


class PostgresIdentityLimiter:
    _ACCOUNT = """
        INSERT INTO public.identity_rate_limit AS quota (identity, bucket, count)
        VALUES (%s, COALESCE(%s::bigint,
            floor(extract(epoch FROM statement_timestamp()) / %s::bigint)::bigint * %s::bigint), 1)
        ON CONFLICT (identity) DO UPDATE SET
            bucket = EXCLUDED.bucket,
            count = CASE WHEN quota.bucket = EXCLUDED.bucket THEN quota.count + 1 ELSE 1 END
        WHERE CASE WHEN quota.bucket = EXCLUDED.bucket THEN quota.count < %s
                   WHEN %s THEN quota.bucket < EXCLUDED.bucket ELSE true END
        RETURNING quota.count
    """

    def __init__(self, connect, *, limit=30, window=60, clock=None):
        if (not callable(connect) or type(limit) is not int or not 1 <= limit < 2**63
                or type(window) is not int or not 1 <= window < 2**63
                or (clock is not None and not callable(clock))):
            raise ValueError("Valid shared limiter configuration required")
        self._connect, self.limit, self.window = connect, limit, window
        self.clock = clock

    def allow(self, issuer, subject):
        # Preserve the existing paper-status bucket representation.
        return self._allow(_identity(issuer, subject), store_window_start=False)

    def allow_owner(self, owner):
        """Use the owner from a verified, currently authorised BFF session."""
        if not isinstance(owner, str) or not re.fullmatch(r"oidc_[a-f0-9]{64}", owner):
            raise PermissionError("Invalid verified identity")
        return self._allow("research_bff:" + owner[5:], store_window_start=True)

    def _allow(self, identity, *, store_window_start):
        try:
            # Store absolute window starts for the BFF so an older statement cannot
            # reopen a window and a coordinated window-size change can recover.
            scale = self.window if store_window_start else 1
            bucket = None if self.clock is None else int(self.clock()) // self.window * scale
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(self._ACCOUNT, (identity, bucket, self.window, scale,
                                                self.limit, store_window_start))
                    row = cur.fetchone()
        except Exception as exc:
            raise RateLimitUnavailable("Shared rate limiter unavailable") from exc
        if row is None:
            raise RateLimitExceeded("Rate limit exceeded")
        if len(row) != 1 or type(row[0]) is not int or not 1 <= row[0] <= self.limit:
            raise RateLimitUnavailable("Shared rate limiter unavailable")
        return True

    def ready(self):
        """Check the dedicated limiter login and its required grants without writing."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT session_user = current_user AND rolcanlogin
                           AND NOT (rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb OR rolreplication)
                           AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members WHERE member = r.oid)
                           AND NOT has_schema_privilege(current_user, 'public', 'CREATE')
                           AND has_table_privilege(current_user, 'public.identity_rate_limit', 'SELECT')
                           AND has_table_privilege(current_user, 'public.identity_rate_limit', 'INSERT')
                           AND has_table_privilege(current_user, 'public.identity_rate_limit', 'UPDATE')
                           AND NOT has_table_privilege(current_user, 'public.identity_rate_limit', 'DELETE,TRUNCATE')
                    FROM pg_catalog.pg_roles AS r WHERE rolname = current_user
                """)
                return cur.fetchone() == (True,)
