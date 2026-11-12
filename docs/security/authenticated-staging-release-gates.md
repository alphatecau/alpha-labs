# Alpha Labs — authenticated staging release gates (research-only)

**Default decision: NO-GO.** This checklist is evidence collection, not deployment approval.

## Database migration
- Schema migration ID: `20261109_paper_security_v1`.
- Operator must explicitly run `apply_schema(connect)` against an authorised, isolated PostgreSQL database.
- Confirm `verify_schema(connect)` and a single recorded migration entry. Re-run to demonstrate idempotence.
- Back up the database and review migration privileges, rollback/restore and lock impact before any shared staging use.
- No automatic production migration, database provisioning or credential changes are authorised.

## Authentication and trusted proxy boundary
- Render or another reverse proxy may supply forwarded headers. Current OIDC WSGI rejects forwarded headers and requires a canonical HTTPS scheme and exact callback Host.
- **Do not remove these checks** to make a proxy deployment work.
- Implement and separately test an ingress adapter that accepts forwarded metadata **only from a configured, authenticated/trusted proxy hop**, removes client-provided forwarded headers, canonicalises scheme/host and rejects ambiguous or conflicting values. Verify origin checks, PKCE/state/nonce, secure cookie and CSRF.
- Direct requests and spoofed `X-Forwarded-Proto`, `Forwarded`, `X-Forwarded-Host` must fail closed.
- Reject unverified Auth0 issuer, audience, signing key or callback configuration; do not log secrets or raw tokens.

## Multi-user staging acceptance
- Two independent authenticated users, separate browsers and sessions; each may see only explicitly provisioned paper accounts.
- Same subject from a different issuer must not gain ownership.
- Unprovisioned, revoked, expired, forged and logged-out sessions must be denied.
- Shared PostgreSQL limiter must enforce one global quota across separate application workers, including concurrent requests; a database outage must fail closed.
- Validate migrations on a disposable database, session persistence across workers, logout, account ownership revocation, CSRF and replay protection.
- Capture request IDs, commit SHA, environment, test evidence and negative-case results without tokens or personal information.
- Verify paper-only responses; no broker orders, live copy execution or payment actions.

## Security review and release decision
- Require review of database privileges, transport TLS, rate-limit resource exhaustion, logging redaction, backup/restore, proxy trust, session expiry and owner-provisioning authority.
- PRs #58–#70 are a dependent **unmerged** research chain; check complete branch ancestry and required CI before any promotion.
- The existing GitHub Actions PostgreSQL container proves isolated database behaviour, **not** Auth0/Render/Sites end-to-end integration.
- Release stays NO-GO until the staging acceptance evidence and independent security review are recorded. No merge or deployment is authorised here.
