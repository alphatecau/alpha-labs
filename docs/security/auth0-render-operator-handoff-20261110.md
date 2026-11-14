# Alpha Labs staging — operator handoff (2026-11-10)

## Observed external configuration (user-supplied screenshots; not live acceptance)

- Auth0 staging Regular Web Application domain: `alpha-labs-dev.au.auth0.com`.
- Callback allowlist: `https://alpha-labs-k869.onrender.com/auth/callback`.
- Logout and web origin allowlists: `https://alpha-labs-k869.onrender.com`.
- Render staging web service: `alpha-labs`, URL `https://alpha-labs-k869.onrender.com`, observed deploy `0c129c6` from `research/render-safe-staging-entry-20261109`.
- Render staging PostgreSQL resource: `alpha-labs-staging-db` (PostgreSQL 16).
- User confirmed Render web-service environment-variable list is empty.
- No evidence that callback endpoint, login, database credentials, RLS roles or session persistence are deployed.

## Code configuration contract (research branch only)

`deployment/auth0_staging_settings.py` currently expects:
- `AUTH0_ISSUER=https://alpha-labs-dev.au.auth0.com/`
- `AUTH0_CLIENT_ID`: use Auth0 staging application ID, not a secret.
- `AUTH0_CALLBACK_URL=https://alpha-labs-k869.onrender.com/auth/callback`
- `ALPHA_BFF_ORIGIN=https://alpha-labs-k869.onrender.com`

`deployment/render_environment_tenant_secrets.py` expects `ALPHA_TENANT_CREDENTIALS_JSON`, populated only after independently verified per-account PostgreSQL LOGIN-role provisioning and credential rotation in an isolated database. Never commit this value or include it in screenshots.

These values describe **research code**, not the deployed health-only staging entry point. Do not enter secrets or enable protected routes until the exact deployment composition and real Auth0 callback have passed security review.

## Mandatory release gates

1. Review current research branch against deployed staging commit; identify and implement an explicit authenticated BFF/WSGI entry point, route-level fail-closed behaviour and secure session store.
2. Verify Auth0 confidential-client token exchange contract, issuer discovery/JWKS rotation, state/nonce/PKCE and CSRF controls.
3. Verify PostgreSQL role provisioning, RLS arbitrary-SQL isolation, credential rotation and account ownership against disposable PostgreSQL 16.
4. Run dedicated unit/integration CI; capture exact commit and check conclusions.
5. Run real staging-tenant browser login/logout/callback and two-account isolation tests **only after separately authorised staging deployment**.
6. Obtain independent security review and explicit staging deployment approval. Keep live execution disabled and existing GPT Site unchanged.

## Operator safety

No wildcard callback URLs, public database DSNs, browser-exposed client secrets, live broker keys, or shared tenant database roles. A successful `/healthz` response is not authentication acceptance. Render secret changes may restart/redeploy services; do not configure them before approval.
