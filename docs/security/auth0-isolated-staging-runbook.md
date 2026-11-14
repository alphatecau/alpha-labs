# Isolated Auth0 staging — operator runbook (NO-GO until acceptance)

## Scope and separation
- Do not change existing Render service `alpha-labs` or its health-only entrypoint.
- Do not use the existing hosted `alpha-labs-staging-db` for destructive/adversarial tests.
- Use a separate, disposable PostgreSQL 16 database and isolated HTTPS service.
- Deploy from a pinned reviewed commit, never an unreviewed branch tip.
- Research GET endpoints only; no order placement, execution, real money or live-trading credentials.

## Dependencies
1. Migration operator installs `public.alpha_oauth_transactions`, `alpha_oidc_sessions` and `public.paper_ownership` schemas from the modules' `SCHEMA` constants in the isolated database.
2. Runtime OAuth state role: only INSERT, DELETE and SELECT (RETURNING) on `alpha_oauth_transactions`; no schema modification or table ownership.
3. Runtime session role: only SELECT, INSERT and DELETE on `alpha_oidc_sessions`; no schema modification or table ownership.
4. Ownership reader role: SELECT on `paper_ownership` only. Provisioning/revocation must use a separate privileged administrative path with an independently verified authority.
5. Research reader: existing tenant-scoped, read-only restricted LOGIN role; no superuser, BYPASSRLS or cross-tenant credential fallback.
6. Inject separate trusted connection factories into `compose_auth0_staging`. A composition factory is not a runnable WSGI deployment entrypoint.
7. Fetch Auth0 JWKS at controlled startup from the pinned HTTPS issuer; fail closed if unavailable. Document restart/refresh procedure for key rotation. Never trust caller-supplied signing keys.
8. Set the existing Auth0 *development* application's exact isolated callback to `https://<isolated-host>/auth/callback`, allowed logout and web origin. Do not change the health-only service's current callback unless explicitly authorised.
9. Inject client secret through the deployment provider's secret manager, not source, command history, screenshots or chat. Rotate any accidentally disclosed secret.

## Release acceptance (all required)
- Latest exact-head GitHub Actions all green, including callback security workflow, CodeQL, secret scan, PostgreSQL and role-isolation checks.
- Verify positive RS256 token, nonce, PKCE, issuer, audience and expiry; deny forged token, replay, expired state, unprovisioned owner and revoked owner.
- Confirm cookie `__Host-` prefix, Secure, HttpOnly, SameSite=Lax, logout revocation and CSRF protections under actual HTTPS.
- Two distinct existing Auth0 development users: browser login, logout, expiration, replay, cross-account denial, concurrent callback and restart recovery.
- Check actual PostgreSQL role grants and `row_security` settings using non-superuser credentials.
- Collect redacted logs and evidence. Independent security review remains required.
- Do not merge or deploy to production; production and live trading remain **NO-GO**.

## Current limitations
- No new isolated Render service or hosted database has been created.
- No real browser or live Auth0 login test has been executed.
- The composition does not include a hosted entrypoint, schema migration runner, refresh scheduler or deployment secret provisioning.
- GitHub Actions' disposable PostgreSQL tests are not equivalent to a live Auth0/browser acceptance test.
