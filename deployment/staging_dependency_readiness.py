"""Explicit, fail-closed staging dependency probes. No DDL, credentials or mutations.

Readiness is not a security attestation: probes verify reachability and selected
database permissions, not tenant isolation or actual browser login acceptance.
"""
from deployment.auth0_trusted_jwks import load_auth0_verifier


def _database_probe(connect, table, *, require_write):
    if not callable(connect):
        raise ValueError("restricted PostgreSQL connector required")
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT current_user, rolsuper, rolbypassrls, rolcreaterole "
                "FROM pg_roles WHERE rolname=current_user")
            role = cursor.fetchone()
            if not role or not isinstance(role[0], str) or any(role[1:]):
                return False
            cursor.execute(
                "SELECT to_regclass(%s) IS NOT NULL, "
                "has_table_privilege(current_user,%s,'SELECT'), "
                "has_table_privilege(current_user,%s,'INSERT'), "
                "has_table_privilege(current_user,%s,'DELETE')",
                (table, table, table, table))
            grants = cursor.fetchone()
            if not grants or len(grants) != 4 or any(type(v) is not bool for v in grants):
                return False
            exists, select, insert, delete = grants
            if not exists or not select:
                return False
            if require_write and not (insert and delete):
                return False
            if not require_write and (insert or delete):
                return False
            cursor.execute("SELECT 1")
            return cursor.fetchone() == (1,)


def create_readiness_check(*, state_connect, session_connect, issuer, client_id,
                           tenant_probe, jwks_fetch=None):
    """Return a per-request readiness callable; all checks must pass exactly.

    tenant_probe must be an independently reviewed check of the restricted
    per-account reader, returning literal True. It must never be a stub in staging.
    """
    if not all(callable(x) for x in (state_connect, session_connect, tenant_probe)):
        raise ValueError("all restricted dependency probes required")
    if not isinstance(issuer, str) or not issuer.startswith("https://"):
        raise ValueError("trusted Auth0 issuer required")
    if not isinstance(client_id, str) or not client_id:
        raise ValueError("trusted Auth0 client ID required")
    if jwks_fetch is not None and not callable(jwks_fetch):
        raise ValueError("trusted JWKS fetcher required")

    def check():
        try:
            if not _database_probe(state_connect, "public.alpha_oauth_state",
                                   require_write=True):
                return False
            if not _database_probe(session_connect, "public.alpha_oidc_sessions",
                                   require_write=True):
                return False
            if tenant_probe() is not True:
                return False
            # Refresh issuer-pinned discovery and JWKS; no stale-key fallback.
            load_auth0_verifier(issuer, client_id, fetch=jwks_fetch)
            return True
        except Exception:
            return False
    return check
