# Auth0 integrated BFF acceptance — AUD $0

## Integration boundaries

The disposable PostgreSQL 16 service stores actual one-time OAuth state and
opaque sessions. The test drives the real WSGI BFF, PKCE controller,
PostgresOAuthStateStore, PostgresOpaqueSessions, AccountRoleResearchReader
and TenantCredentialBroker.

Injected Auth0 code exchange and ID-token verifier are deterministic doubles;
the research connection is a SQL-contract fake that checks the expected
verified tenant role. Therefore these tests are **not** evidence of actual
Auth0 network login, JWT signature validation in the integrated flow, or
database-enforced tenant row-level security. Those have separate unit/CI gates
and remain subject to hosted end-to-end acceptance.

## Acceptance cases

- Login produces an HTTPS PKCE redirect and browser-bound state cookie
- Callback consumes durable state, creates a session and redirects
- Research runs and summary are read-only and scoped to the verified owner
- Callback replay is rejected without repeating token exchange
- Missing and mismatched browser-state cookies are rejected
- Missing session and revoked/deprovisioned owner are denied
- Cross-origin logout is rejected; same-origin logout revokes the session
- POST research and order endpoints are absent; health reports trading disabled

## Release decision

Green CI is necessary, not sufficient. No deployment, production trading,
independent review or hosted Auth0 acceptance is authorised by this PR.
