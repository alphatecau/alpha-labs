# Authenticated read-only staging: security review and deployment hold

Status: **NOT APPROVED FOR DEPLOYMENT**. Research-only draft PR #74.
The current Render service runs the health-only probe and must remain unchanged.

## Verified in GitHub Actions
- Python offline research tests, Sites tests, staging composition unit tests and isolated PostgreSQL 16 integration tests passed at commit b921f8395fc6d7f18f6aa1be0ab81c34724296c1.
- OIDC session creation, cross-connection persistence, revocation, expiry and concurrent single-use state consumption exercised against an ephemeral database.
- Fail-closed WSGI routing rejects trading routes, unexpected hosts, forwarded headers and untrusted REMOTE_ADDR in unit tests.

## Critical deployment blockers
1. **Render ingress peer identity is unverified.** The application uses REMOTE_ADDR with operator-supplied trusted CIDRs. Private-address ranges or broad CIDRs are NOT sufficient proof that the request originated at an authenticated Render reverse proxy. No public ingress can be enabled until the immediate peer, forwarding semantics and inability to bypass the proxy are independently demonstrated. Do not use 0.0.0.0/0, ::/0 or arbitrary private CIDRs as a workaround.
2. **No persistent staging PostgreSQL database is provisioned.** CI's disposable PostgreSQL is not a staging data store. Verify TLS, least-privilege roles, backup/retention, migrations, schema ownership and transaction behaviour before activation. Do not fall back to SQLite or in-memory sessions on an ephemeral Render instance.
3. **Auth0 tenant configuration is absent/unverified.** Verify confidential OIDC client, exact HTTPS callback and logout origins, issuer/audience, nonce, PKCE, state, JWKS and rotation. Store secrets server-side only. Do not put credentials in browser JavaScript, GitHub, logs or Sites.
4. **Account data source and isolation are unverified.** The WSGI composition injects an accounts adapter; no production-quality, tenant-scoped account store has been established. Demonstrate issuer+subject binding, explicit owner provisioning, cross-account denial, revocation, and no disclosure via read-only responses.
5. **End-to-end security review incomplete.** Test two independent identities, session fixation, cookie scope, CSRF on logout, stale cookies, replay, concurrent requests, rate limiting, proxy spoofing, error handling, and no executable trading routes under the actual hosting topology.

## Staging acceptance evidence required
- Record exact commit, deploy ID, configuration revision and timestamp.
- Demonstrate health probe remains operational and no research endpoints are exposed until the gates pass.
- Run real browser login/callback/logout on Android, then test expired, revoked and forged sessions.
- Prove account A cannot read account B, including after restart and concurrent requests.
- Prove broker connectivity, live trading and copy execution remain disabled.
- Independently review secret storage and access controls before enabling any authenticated endpoint.

## Decision
**HOLD**. No merge, Render deploy, database provisioning, Auth0 secret changes, paid services or trading activation without explicit authorisation and documented acceptance.
