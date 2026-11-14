# Alpha Labs — Preliminary security review (not independent sign-off)

Review scope: PR #122 reconstructed identity/ownership modules, staging BFF, tenant broker.
Review method: static source inspection and existing disposable PostgreSQL CI evidence.
Reviewer: AI-assisted preliminary assessment; **not an independent human security review**.

## Findings

### SEC-01 — HIGH: VerifiedPrincipal is not a verified authentication capability
`alpha_lab/research/paper_account_service.py` exposes a public dataclass that accepts any syntactically valid subject and HTTPS issuer. `PostgresPaperOwnership.provision()` accepts this dataclass and inserts an active owner record. A caller with access to provisioning can therefore construct a principal for an arbitrary subject and issuer; the type alone does not prove that an OIDC token was validated.

Required remediation: restrict provisioning to a trusted server-side, authenticated administrative pathway and bind the principal to a successfully validated OIDC result. Prove that untrusted HTTP data cannot instantiate a principal that authorises provisioning. Avoid relying on dataclass type checking as the security boundary.

### SEC-02 — HIGH: Provisioning can reactivate a revoked owner
`PostgresPaperOwnership.provision()` uses `ON CONFLICT ... DO UPDATE SET active=true`. Repeated provisioning of the same identity reactivates access after `revoke_owner_id()`. Require a separate audited reactivation operation with explicit authority, or fail closed on revoked records. Test revocation persistence and re-provisioning denial.

### SEC-03 — MEDIUM: Ownership schema is not an operational migration
`SCHEMA` creates tables, but does not define restricted application roles, grant boundaries, migration sequencing, or audit records. The disposable test uses privileged setup credentials. Before staging, implement least-privilege migrations and independently review actual role grants.

### SEC-04 — REVIEW REQUIRED: OAuth callback and trusted ingress
`StagingResearchBFF` delegates OIDC validation to an injected controller. Static inspection cannot prove the real Auth0 PKCE/state/nonce lifecycle, callback URL binding, proxy headers, TLS termination, and logout behaviour. A real browser/IdP integration is mandatory.

## Evidence and decision
At commit `673101f892bfdc3add64aec964b245616b4a5523`, 13 reported GitHub Actions workflows succeeded, including disposable database and BFF tests. These tests do not resolve SEC-01/02 or verify real Auth0 browser interaction.

**PRELIMINARY_SECURITY_REVIEW: FAIL (two high-severity findings).**
**INDEPENDENT_REVIEW: PENDING.**
**PRODUCTION_RELEASE: NO-GO.**

## Required real Auth0 test prerequisites
- Dedicated disposable Auth0 tenant/application with known issuer, client ID, exact HTTPS callback/logout origins, and two non-production test users
- Isolated HTTPS staging BFF wired to the actual verified OIDC controller and restricted PostgreSQL credentials
- Browser automation against the disposable identity provider: login, PKCE/state/nonce, tampered callback, session cookie flags, logout, expiry, replay, two-user separation and revocation
- Sanitised CI artifacts, no real tokens/secrets in logs, independent reviewer sign-off

Do not deploy to the existing Render service or modify the hosted database to satisfy this plan without separate approval.
