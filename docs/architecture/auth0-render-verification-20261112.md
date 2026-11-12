# Alpha Labs — Auth0/Render configuration verification, 2026-11-12

Status: CONFIGURATION IDENTIFIED; BACKEND NOT DEPLOYED. No secrets collected or modified.

## Operator-confirmed Auth0 application
- Tenant: alpha-labs-dev, Australia; issuer: https://alpha-labs-dev.au.auth0.com/
- Application: second "Alpha Labs Staging" Regular Web Application
- Client ID: DP8p06i6yDAI5RLR0veQhVL4KXPM58kj
- Operator confirmed Auth0 accepted the callback and logout settings ("Application settings updated").
- Callback: https://alpha-labs-k869.onrender.com/auth/callback
- Logout URL: https://alpha-labs-k869.onrender.com
- Web origins: operator earlier reported saved; not independently confirmed in final screenshot.
- Client secret: NOT COLLECTED; no secret is to be committed.

## Render service, current deployment
- Existing service srv-dbop6f3bc2fs73cqfksg on research/render-safe-staging-entry-20261109, commit 0c129c6.
- Existing environment variables and secret files: none visible in operator screenshots.
- Staging probe deployment/staging_probe.py implements only GET /healthz. No callback, token exchange, session persistence, owner orders or storage.
- Adding Auth0 variables to this service now would not enable login and may trigger a deploy/restart. DO NOT ADD THEM YET.

## Required backend composition before any secrets
1. An executable WSGI entrypoint must instantiate the existing staging Auth0 flow/controller, durable PKCE state/session repository, tenant-specific PostgreSQL reader, verified owner authoriser and shared limiter. Explicitly reject missing dependencies.
2. Exact-origin HTTPS and trusted proxy validation; deny spoofed forwarded headers and cookie/session replay.
3. Automated tests for login/callback/logout/revocation, wrong owner, cross-account reads, fail-closed DB failure and shared quotas; then actual Auth0 staging tenant browser acceptance.
4. Owner-paper persistent journal and protected checkpoint/restore must not use ephemeral free web filesystem or expiring free PostgreSQL as sole durable record.
5. Independent review/approval of #103–#105, including B310/B104 findings and current-head CI.

## Free-only disposition
Existing free web service may remain a health probe. No authenticated owner paper release until persistence/recovery and ingress gates are met. The free database has a recorded 2026-12-09 expiry; verify renewal/backup lifecycle before relying on it. Do not provision paid resources without user budget change.

## Next operator action
None in Render now. Preserve existing service and secrets. Once the executable BFF is independently accepted, configure the exact variables via Render secret manager, not GitHub or chat.
