"""Explicit authenticated staging bootstrap; never auto-deploy or auto-migrate.

The operator must supply a reviewed ownership registry and principal factory.
State/session credentials are restricted and distinct from tenant reader roles.
"""
from deployment.auth0_refreshing_verifier import RefreshingAuth0Verifier
from deployment.auth0_staging_settings import staging_auth0_settings
from deployment.postgres_pkce_state_store import PostgresPKCEStateStore
from deployment.staging_authenticated_assembly import assemble


def build_authenticated_application(*, environ, ownership, principal_factory,
                                    state_connect, session_connect, tenant_connect,
                                    verifier_factory=RefreshingAuth0Verifier):
    """Construct WSGI app only after all security dependencies are supplied.

    Connectors must be configured externally with independent restricted roles.
    No credential fallback, database migration, or network listener is created.
    """
    config = staging_auth0_settings(environ)
    if ownership is None or not callable(getattr(ownership, "require", None)):
        raise ValueError("reviewed ownership registry required")
    if not callable(principal_factory):
        raise ValueError("reviewed principal factory required")
    if not all(callable(x) for x in (state_connect, session_connect, tenant_connect)):
        raise ValueError("separate restricted PostgreSQL connectors required")
    if not callable(verifier_factory):
        raise ValueError("trusted verifier factory required")
    verifier = verifier_factory(config["issuer"], config["client_id"])
    if not callable(verifier):
        raise ValueError("trusted verifier unavailable")
    return assemble(
        verify_token=verifier,
        ownership=ownership,
        principal_factory=principal_factory,
        state_store=PostgresPKCEStateStore(state_connect),
        session_connect=session_connect,
        tenant_connect=tenant_connect,
        environ=environ,
    )


# Deliberately no module-level 'application': ownership, role provisioning,
# migrations and real Auth0 acceptance are mandatory before enabling traffic.
