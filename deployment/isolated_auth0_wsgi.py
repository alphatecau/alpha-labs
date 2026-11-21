"""Fail-closed WSGI entrypoint for a *new* isolated research-only staging service.

Not deployed by this commit. All values are server-side environment variables.
The existing health-only Render service must not point at this entrypoint.
"""
import json
import logging
import os
import threading
from urllib.parse import urlsplit

from deployment.research_dashboard import access_message
from deployment.account_role_research_reader import AccountRoleResearchReader
from deployment.isolated_auth0_role_audit import audit_runtime_roles
from deployment.tenant_credential_broker import TenantCredentialBroker


def build_isolated_app(env=None, *, pg_connect=None):
    """Build only with explicitly isolated resources and audited restricted roles."""
    config = os.environ if env is None else env
    required = (
        "ALPHA_ISOLATED_STAGING", "AUTH0_ISSUER", "AUTH0_CLIENT_ID",
        "AUTH0_CLIENT_SECRET", "ALPHA_STAGING_ORIGIN", "ALPHA_OAUTH_DSN",
        "ALPHA_SESSION_DSN", "ALPHA_OWNERSHIP_DSN", "ALPHA_AUDIT_DSN",
        "ALPHA_OAUTH_ROLE", "ALPHA_SESSION_ROLE", "ALPHA_OWNERSHIP_ROLE",
        "ALPHA_TENANT_CREDENTIALS_JSON",
    )
    if config.get("ALPHA_ISOLATED_STAGING") != "true":
        raise PermissionError("explicit isolated staging approval required")
    if any(not isinstance(config.get(k), str) or not config[k] for k in required):
        raise PermissionError("missing isolated staging configuration")
    origin = urlsplit(config["ALPHA_STAGING_ORIGIN"])
    if (origin.scheme != "https" or not origin.hostname or origin.username or
            origin.password or origin.path not in ("", "/") or origin.query or
            origin.fragment or origin.hostname == "alpha-labs-k869.onrender.com"):
        raise PermissionError("dedicated HTTPS staging hostname required")
    if len({config["ALPHA_OAUTH_DSN"], config["ALPHA_SESSION_DSN"],
            config["ALPHA_OWNERSHIP_DSN"], config["ALPHA_AUDIT_DSN"]}) != 4:
        raise PermissionError("separate runtime and audit database credentials required")
    if pg_connect is None:
        import psycopg
        pg_connect = psycopg.connect
    credentials = json.loads(config["ALPHA_TENANT_CREDENTIALS_JSON"])
    if not isinstance(credentials, dict):
        raise PermissionError("invalid server-side tenant credential mapping")

    def connect_for(name):
        return lambda: pg_connect(config[name], connect_timeout=5)

    audit_runtime_roles(
        connect_for("ALPHA_AUDIT_DSN"),
        oauth_role=config["ALPHA_OAUTH_ROLE"],
        session_role=config["ALPHA_SESSION_ROLE"],
        ownership_role=config["ALPHA_OWNERSHIP_ROLE"])

    for dsn_key, role_key in (("ALPHA_OAUTH_DSN", "ALPHA_OAUTH_ROLE"),
                              ("ALPHA_SESSION_DSN", "ALPHA_SESSION_ROLE"),
                              ("ALPHA_OWNERSHIP_DSN", "ALPHA_OWNERSHIP_ROLE")):
        with connect_for(dsn_key)() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT session_user, current_user")
                if cur.fetchone() != (config[role_key], config[role_key]):
                    raise PermissionError("runtime DSN does not match audited restricted role")

    from alpha_lab.research.postgres_paper_security import PostgresPaperOwnership

    ownership = PostgresPaperOwnership(connect_for("ALPHA_OWNERSHIP_DSN"))

    def secret_for(owner):
        # A missing owner is never mapped to a shared database account.
        if owner not in credentials:
            raise PermissionError("tenant not provisioned")
        return credentials[owner]

    broker = TenantCredentialBroker(secret_for, pg_connect)
    # Optional operator preflight on the isolated service. It reads no account data.
    probe_owner = config.get("ALPHA_STAGING_VERIFY_READER")
    if probe_owner:
        try:
            with broker(probe_owner):
                pass
        except Exception as exc:
            # Never log connection strings, passwords, account identifiers or raw exceptions.
            known_causes = ("certificate", "password authentication", "timeout", "hostname",
                            "read-only", "tenant table policy", "database identity", "not provisioned",
                            "invalid tenant credential", "connection refused")
            cause = next((label for label in known_causes if label in str(exc).lower()), "unknown")
            logging.getLogger(__name__).error("staging_reader_check failed type=%s sqlstate=%s cause=%s",
                                             type(exc).__name__, getattr(exc, "sqlstate", None), cause)
        else:
            logging.getLogger("gunicorn.error").info("staging_reader_check passed")
    reader = AccountRoleResearchReader(broker)
    from deployment.auth0_staging_composition import compose_auth0_staging
    return compose_auth0_staging(
        issuer=config["AUTH0_ISSUER"],
        client_id=config["AUTH0_CLIENT_ID"],
        client_secret=config["AUTH0_CLIENT_SECRET"],
        origin=config["ALPHA_STAGING_ORIGIN"],
        oauth_connect=connect_for("ALPHA_OAUTH_DSN"),
        session_connect=connect_for("ALPHA_SESSION_DSN"),
        ownership=ownership, reader=reader)


# Hosting must explicitly select this WSGI target on a NEW isolated service.
# No network, database or secret access occurs when this module is imported.
_lock = threading.Lock()
_app = None


def application(environ, start_response):
    global _app
    if _app is None:
        with _lock:
            if _app is None:
                try:
                    _app = build_isolated_app()
                except Exception:
                    body = b'{"error":"research_auth_unavailable"}'
                    content_type = "application/json"
                    if (environ.get("REQUEST_METHOD") == "GET"
                            and environ.get("PATH_INFO") in ("/", "/dashboard", "/auth/login", "/auth/callback")
                            and "text/html" in environ.get("HTTP_ACCEPT", "")):
                        body = access_message("Sign-in temporarily unavailable",
                                              "Your research account could not be opened. Please try again later.")
                        content_type = "text/html; charset=utf-8"
                    start_response("503 Service Unavailable", [
                        ("Content-Type", content_type), ("Content-Length", str(len(body))),
                        ("Cache-Control", "no-store"), ("Referrer-Policy", "no-referrer"),
                        ("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"),
                        ("X-Content-Type-Options", "nosniff")])
                    return [body]
    return _app(environ, start_response)
