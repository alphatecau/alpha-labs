# Auth0 staging acceptance and independent review — 9 November 2026

Status: **NO-GO**. This is a source-level assessment, not an independent external penetration test.

## Verified GitHub evidence
- PR #61 head 478dfc61fb65a90988f68e74fcd4b14fb9787274
- Offline research: https://github.com/alphatecau/alpha-labs/actions/runs/42587654591 — success
- Sites: https://github.com/alphatecau/alpha-labs/actions/runs/42587654618 — success
- OIDC security: https://github.com/alphatecau/alpha-labs/actions/runs/42587654637 — success
- All tests use synthetic identity and local fixtures; **no live Auth0 tenant smoke test**.

## Confirmed architectural gaps / security blockers
1. The OIDC WSGI adapter is not mounted by a reviewed production/staging entry point. Do not deploy or advertise live login.
2. Session storage is local SQLite. Multiple Render instances/ephemeral filesystems would cause inconsistent login, lost sessions, and possible persistence failure. Select a protected durable shared database, use migrations, per-user constraints, concurrency/lock tests, cleanup and backups.
3. The callback exchanges an authorization code and verifies the ID token using pinned JWKS, but real Auth0 compatibility, key rotation, audience/authorized-party behaviour, tenant settings and logout semantics are untested.
4. The paper status adapter assumes a pre-opened server-owned account. No audited account provisioning, lifecycle, session-to-account ownership registry or durable paper runtime coordination is implemented.
5. The HTTPS gate relies on WSGI scheme supplied by a **trusted** reverse proxy. Direct ingress and spoofed forwarded headers must be blocked and tested.
6. Session cookie CSRF handling is incomplete for any future state-changing routes; Origin checking protects only POST logout. Adopt explicit CSRF tokens and same-origin checks before write routes.
7. No brute-force/rate-limit controls, per-IP request caps, login flood bounds, bounded token exchange concurrency or account-lockout strategy have been verified.
8. No authenticated browser tests against a real tenant, non-owner user, natural session expiry, browser cookie behaviour or production-like staging database.
9. No key rollover/revocation runbook or verified JWKS refresh mechanism.
10. No independent security reviewer has approved the architecture.

## Release gate
- Keep PRs #58–61 in draft; do not merge, deploy, enable trading or modify secrets.
- Independently verify each missing item and attach reproducible evidence to its PR.
- For any eventual deployment, request explicit authorisation and provision real tenant configuration using a secret manager; never commit secrets.
- Retain research-only and read-only API restrictions until independent approval.
