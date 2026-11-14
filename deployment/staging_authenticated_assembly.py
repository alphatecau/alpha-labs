"""Research-only staging assembly; never activate without approved configuration.

Builds an authenticated WSGI application using a trusted OIDC verifier and
separate restricted PostgreSQL session and tenant roles. No credentials in code.
"""
import os
from deployment.auth0_login_flow import Auth0LoginFlow
from deployment.auth0_session_controller import Auth0SessionController
from deployment.auth0_staging_settings import staging_auth0_settings
from deployment.postgres_opaque_sessions import PostgresOpaqueSessions
from deployment.staging_authenticated_bff import StagingResearchBFF
from deployment.account_role_research_reader import AccountRoleResearchReader
from deployment.tenant_credential_broker import TenantCredentialBroker
from deployment.render_environment_tenant_secrets import RenderEnvironmentTenantSecrets


def assemble(*, verify_token, ownership, principal_factory, state_store,
             session_connect, tenant_connect, rate_limiter, environ=None):
    """Dependencies must be trusted; no browser-supplied credential selectors."""
    env = os.environ if environ is None else environ
    config = staging_auth0_settings(env)
    if not callable(verify_token) or ownership is None or not callable(principal_factory):
        raise ValueError("trusted OIDC verifier and ownership dependencies required")
    if not callable(getattr(ownership, "require_owner_id", None)):
        raise ValueError("current owner-ID authorization required")
    if state_store is None or not callable(session_connect) or not callable(tenant_connect):
        raise ValueError("persistent state and restricted database connectors required")
    secret = env.get("AUTH0_CLIENT_SECRET")
    if not isinstance(secret, str) or len(secret) < 16:
        raise ValueError("staging confidential-client secret required")
    sessions = PostgresOpaqueSessions(session_connect)
    flow = Auth0LoginFlow(issuer=config["issuer"], client_id=config["client_id"],
                          redirect_uri=config["redirect_uri"], state_store=state_store)
    controller = Auth0SessionController(flow, verify_token, sessions, ownership,
                                        principal_factory, client_secret=secret)
    provider = RenderEnvironmentTenantSecrets(env)
    broker = TenantCredentialBroker(provider, tenant_connect)
    reader = AccountRoleResearchReader(broker)
    return StagingResearchBFF(flow, controller, sessions, reader, origin=config["bff_origin"],
                              rate_limiter=rate_limiter,
                              authorize_owner=lambda owner: ownership.require_owner_id(owner, "primary"))

# Intentionally no module-level WSGI 'application': deployment must explicitly
# supply a verified issuer/JWKS loader, restricted database connections,
# persistent state store and independent ownership registry.
