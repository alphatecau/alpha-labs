# Security acceptance status — 2026-11-16

Baseline inspected: `c025992ebd6126fb1fa833b81fb3dcac7e75f764`.

## Auth0
Correct RSA import is present. Recent commits #124–#130 describe signed-token, PKCE, replay, session recovery, restricted roles and outage-hardening tests. These are **implementation evidence**, not fresh runtime or independent review evidence. Re-execute exact-head tests and adversarial cases.

## PostgreSQL
Commit `c9ff33b5c2f9ff7884d367ee037948d027487c65` (#127) adds disposable PostgreSQL 16 restricted-login and FORCE RLS acceptance according to commit metadata. No fresh real restricted-role session was executed during this audit. Confirm separate runtime/audit/admin identities, denied cross-tenant reads/writes, forged tenant GUC, role switching, revocation and recovery in disposable CI.

## High-priority trust boundaries
The repository's existing `docs/security/pr122-preliminary-security-review.md` records SEC-01: `VerifiedPrincipal` dataclass is syntactically validated but not cryptographic proof of identity. Review provisioning authority and verify no untrusted route can authorise owner creation. The observed `VerifiedPrincipal` source confirms it is a public constructible dataclass.

PR #135 documents a potential fail-open concurrent refresh race in the optional dual-source paper market-data gate. Verify its fix with deterministic concurrency tests and independent review before accepting that gate for research-only use.

## Hosted staging
**NO-GO / NOT VERIFIED.** No real browser Auth0 login/logout/expiry, hosted restricted-role SQL, operational recovery or independent sign-off was performed during this audit. Do not deploy or expose hosted staging based on offline tests.

## Live trading
**NO-GO.** No live exchange execution or capital authorisation.
