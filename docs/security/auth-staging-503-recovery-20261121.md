# Auth staging 503 — verified recovery preflight (21 November 2026)

## Evidence
- Render service `srv-dc0eo7rm8hqs73e9a2u0` deployed commit `09665382053dda7d71ffa4c151e71b488da9d24a` successfully at 02:18:03 UTC.
- HTTP GET / returned 503 at 02:19 UTC, with `{"error":"research_auth_unavailable"}`.
- Deployed `deployment/isolated_auth0_wsgi.py` catches all exceptions from `build_isolated_app()` and returns this generic 503. It deliberately does not log the underlying exception. Do not assume a specific missing key without checking.
- Operator screenshots show four variables; source requires 13 nonempty variables, a literal `ALPHA_ISOLATED_STAGING=true`, four distinct DSNs, and restricted role audit. Screenshots alone cannot establish values or full secret configuration.
- Existing Render `alpha-labs-staging-db` is available, but has no external IP allowlist; hosted Render MCP read-only SQL cannot connect. **Do not open the allowlist to the internet.**
- Existing security runbooks require a separate disposable isolated database; do not reuse the shared staging database or production credentials.

## Required environment keys (names only; never record values)
`ALPHA_ISOLATED_STAGING`, `AUTH0_ISSUER`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET`, `ALPHA_STAGING_ORIGIN`, `ALPHA_OAUTH_DSN`, `ALPHA_SESSION_DSN`, `ALPHA_OWNERSHIP_DSN`, `ALPHA_AUDIT_DSN`, `ALPHA_OAUTH_ROLE`, `ALPHA_SESSION_ROLE`, `ALPHA_OWNERSHIP_ROLE`, `ALPHA_TENANT_CREDENTIALS_JSON`.

## Safe execution gates
1. Confirm the selected Auth0 client ID matches the application with the isolated callback; do not expose secrets.
2. Verify dedicated disposable database availability within approved AUD 0 budget. If unavailable, STOP; no shared-database fallback.
3. Back up and document the dedicated database before schema changes. Migration operator must be distinct from runtime identities.
4. Apply reviewed OAuth, opaque session and paper ownership schema migrations to dedicated database only.
5. Provision three separate restricted LOGIN roles: OAuth SELECT/INSERT/DELETE only, sessions SELECT/INSERT/DELETE only, ownership SELECT only. Audit role attributes, grants and table ownership using `audit_runtime_roles`.
6. Provision an independent audit identity and distinct restricted tenant research reader(s) with FORCE RLS; no privileged credential fallback.
7. Configure secret values server-side, including exact HTTPS staging origin; never store them in GitHub, chat, screenshots or logs.
8. Run negative configuration tests and actual restricted-role SQL checks. Only then deploy reviewed pinned commit to isolated staging.
9. Verify /healthz, real Auth0 login/logout, replay denial, session expiry, tenant isolation, restart and recovery. Record redacted evidence and rollback instructions.
10. Production and live trading remain NO-GO pending independent review.

## Current blockers
- Hosted connector cannot perform PostgreSQL DDL or query a database with an empty external allowlist.
- No independently verified dedicated disposable database, migration role, tenant provisioning or positive browser login.
- Do not trigger another deploy merely to wait for the 503 to disappear.

This document is a recovery plan and evidence record, **not** proof that the application is fixed.
