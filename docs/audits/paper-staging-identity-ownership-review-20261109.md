# Identity and ownership review — 2026-11-09

## Verified from branch source

- HTTP status checks a short-lived HMAC bearer token with pinned issuer and
  audience; this is **research-only**, not a production identity provider.
- The staging factory provisions the configured owner from server-side settings.
- The new `paper_ownership.py` records owner grants in SQLite and requires an
  active grant on every status lookup. Revocation is persistent and ordinary
  provisioning does not silently reactivate revoked grants.
- User-controlled subject and account query parameters are not accepted by the
  read-only WSGI route. No order/enable route exists.

## Open security blockers

- A trusted external identity provider and verifiable token lifecycle
  (key rotation, revocation, issuer/audience validation, replay controls).
- Session and account ownership lifecycle: administrator-controlled grants,
  onboarding, offboarding, migrations, backup/restore and audit records.
- SQLite concurrency/locking and atomicity across owner registry and journal
  are not proven for multi-worker or multi-instance deployment.
- The in-process registry remains a prototype; no cross-tenant HTTP integration
  tests against a real ingress or GPT Site have run.
- TLS, rate limiting, WAF, observability, availability and incident response
  require deployment-specific acceptance tests.
- Render blueprint has not been applied or verified against Render deployment.

## Decision

**NO-GO for public or production deployment.** Continue offline research only.
No live-copy trading, credentials or broker connection.

## Additional negative tests

The HTTP contract suite now tests that owner revocation immediately denies
status access and remains denied after the staging factory reopens the SQLite
registry. It also rejects spoofed owner headers for non-owner signed tokens.
These tests do not establish real identity-provider security or production
multi-process database safety. CI outcome must be checked separately.
