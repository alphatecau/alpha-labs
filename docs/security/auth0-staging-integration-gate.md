# Auth0 staging integration — release gate

Status: **CODE CANDIDATE ONLY / NO DEPLOYMENT / NO LIVE TRADING**.

## Implemented in PR #122
- Server-side PKCE S256 and unpredictable state/nonce
- PostgreSQL OAuth transaction store with atomic consume and expiry
- Auth0 authorisation-code exchange over HTTPS without redirects
- RS256 JWKS signature, issuer, audience, nonce and expiry verification
- Account authorisation before issuing opaque, HttpOnly Secure SameSite=Lax sessions
- Offline negative tests for replay, expired state, unprovisioned identities and forged tokens

## Critical acceptance prerequisites
1. Verify the complete CI run on the latest commit, including the Auth0 callback workflow.
2. Independently review the callback code, identity verification, nonce, cookie and transaction handling.
3. Add tested, reviewed server composition that injects a restricted PostgreSQL state/session store, pinned Auth0 issuer/client ID, securely obtained client secret, trusted JWKS retrieval with rotation, token exchanger and an ownership authoriser. **No such hosted composition is yet deployed.**
4. Ensure provisioning is performed only by an explicitly authenticated administrative path. The verified callback should *authorise* existing ownership, not automatically provision arbitrary users.
5. Configure a **new isolated HTTPS staging endpoint** and register its exact callback/logout/origin values in the existing Auth0 development application. Do not reuse the current health-only Render service or hosted database.
6. Execute actual browser logins for two existing disposable Auth0 users; prove successful login, PKCE/state/nonce binding, logout, expiry, replay rejection, session theft resistance, tenant A/B isolation and revocation.
7. Capture sanitised evidence and obtain independent human security sign-off.

Do not put client secrets, refresh tokens, test passwords or session cookies in GitHub or screenshots. Do not merge or deploy without the separate approvals required by the project.
