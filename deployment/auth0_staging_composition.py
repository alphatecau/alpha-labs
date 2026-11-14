"""Explicit Auth0 staging composition; no environment or network side effects.

The caller supplies restricted DB connections, a tenant-isolated research
reader, verified Auth0 configuration, and a *pre-provisioned* ownership gate.
No account is provisioned on login. This factory is not a deploy entrypoint.
"""
from deployment.auth0_pkce_callback import Auth0PKCEFlow, Auth0CallbackController
from deployment.auth0_code_exchange import Auth0CodeExchanger
from deployment.auth0_verified_identity import Auth0IDTokenVerifier
from deployment.auth0_jwks import fetch_auth0_jwks
from deployment.postgres_oauth_state import PostgresOAuthStateStore
from deployment.postgres_opaque_sessions import PostgresOpaqueSessions
from deployment.staging_authenticated_bff import StagingResearchBFF


def compose_auth0_staging(*, issuer, client_id, client_secret, origin, jwks=None,
                          oauth_connect, session_connect, ownership,
                          reader, account_key="primary"):
    """Return WSGI app only when all trusted dependencies are explicitly supplied."""
    if oauth_connect is session_connect:
        raise ValueError("separate restricted OAuth and session DB connections required")
    if not callable(oauth_connect) or not callable(session_connect):
        raise ValueError("restricted DB connection factories required")
    if ownership is None or not callable(getattr(ownership, "require_owner_id", None)):
        raise ValueError("trusted pre-provisioned ownership gate required")
    callback = origin.rstrip("/") + "/auth/callback"
    flow = Auth0PKCEFlow(
        issuer=issuer, client_id=client_id, redirect_uri=callback,
        state_store=PostgresOAuthStateStore(oauth_connect))
    sessions = PostgresOpaqueSessions(session_connect)
    trusted_keys = fetch_auth0_jwks(issuer) if jwks is None else jwks
    verifier = Auth0IDTokenVerifier(issuer=issuer, client_id=client_id, jwks=trusted_keys)
    exchanger = Auth0CodeExchanger(
        issuer=issuer, client_id=client_id, client_secret=client_secret)

    def authorised(principal):
        owner = PostgresOpaqueSessions._owner(principal.subject, principal.issuer)
        try:
            return ownership.require_owner_id(owner, account_key) is True
        except PermissionError:
            return False

    controller = Auth0CallbackController(
        flow=flow, exchange_code=exchanger, token_verifier=verifier,
        sessions=sessions, authorise_principal=authorised)
    return StagingResearchBFF(
        flow, controller, sessions, reader, origin=origin,
        authorize_owner=lambda owner: ownership.require_owner_id(owner, account_key))
