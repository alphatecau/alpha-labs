# Alpha Labs staging acceptance gate (2026-11-10)

**Decision: NOT APPROVED FOR DEPLOYMENT.** This is a research-only gate; no live trading or brokerage routes.

## Evidence verified
- Auth0 application: Alpha Labs Staging, Regular Web Application, tenant `alpha-labs-dev.au.auth0.com`. Client ID and callback were checked against user-supplied dashboard screenshots; secret value was neither collected nor copied.
- Callback configured: `https://alpha-labs-k869.onrender.com/auth/callback`; logout origin and web origin: `https://alpha-labs-k869.onrender.com`.
- GitHub Actions for commit `5e7ae7f7db6948c88cc1e9c73a248c65eb526ea6`: authenticated read-only API, offline research, and Sites v0.3 workflows succeeded.
- Render service `srv-dbop6f3bc2fs73cqfksg` is still on `research/render-safe-staging-entry-20261109` with start command `python deployment/staging_probe.py`; auto-deploy is disabled. Earlier deployment failed because that file was absent.
- Render PostgreSQL `alpha-labs-staging-db` is available in Singapore, PostgreSQL 16, and has no public IP allow-list entries. **Do not use this database for destructive provisioning acceptance.**

## Unresolved blocking controls
1. Implement an executable WSGI server bootstrap with trusted JWKS verification, independent account ownership, persistent PKCE/session stores, and restricted tenant credential lookup. The assembly intentionally has no module-level `application`.
2. Verify a production-capable WSGI start command and startup/health failure modes. A healthy response must not falsely imply readiness of dependencies.
3. Perform role creation, rotation, revocation, and cross-tenant SQL adversarial tests against a **disposable** PostgreSQL instance only. Verify role membership, read-only enforcement and no superuser/BYPASSRLS privileges.
4. Independent review of OAuth state/PKCE permissions, JWKS refresh/revocation handling, trusted HTTPS proxy headers, session fixation/expiry, tenant isolation, denial of trading routes, and operational logging.
5. Confirm Auth0 client secret exists in server-side Render environment without printing or committing it; verify issuer, callback, and TLS.
6. After all gates pass and explicit approval, update Render branch/start command and deploy. Then run real Auth0 browser acceptance with two independent test accounts: login, callback, logout, expiry, cross-account isolation, and negative cases.

## Prohibited shortcuts
Do not run the assembly module as a server, do not put secrets in GitHub, do not use staging PostgreSQL for destructive acceptance, do not weaken fail-closed checks, do not deploy from a branch with unverified CI, and do not enable trading.
