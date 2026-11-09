# Paper trading server integration contract (research only)

## Current implementation
`PaperAccountService` partitions paper journals by a SHA-256-derived filename
from issuer, subject and account, and defaults new accounts to HALT. It requires
a `VerifiedPrincipal` object, but **this is only a Python data type and is
forgeable by code in the same process**. It is NOT authentication.

The current implementation is an offline service prototype, not a deployable
authenticated web API. The underlying runtime is not multi-process safe and
does not yet provide robust database ownership, locking, or per-request
transactional idempotency.

## Required production boundary
1. Authenticate every request using a verified, server-side session or JWT
   signature with pinned issuer, audience, expiry and key rotation.
2. Derive subject from the validated session; never accept a subject, issuer,
   account ownership or trading authority from client JSON.
3. Authorise account ownership against a server-owned database, including
   tenant isolation and revocation.
4. Enforce CSRF controls for cookie-based sessions; apply origin restrictions,
   rate limits and structured audit logs.
5. Server-side idempotency keys, account-level locking, journal durability,
   crash/replay tests and per-user quotas.
6. Independently verify NAV, costs, quote timestamps and portfolio risk.
7. Integrate website read-only status first; keep enable/execute API disabled
   until complete authenticated end-to-end negative tests.
8. No live broker adapters, live copy orders or secrets in browser bundles.

## Release decision
**NO-GO**. No authenticated HTTP API, browser integration or deployment has
been completed. Passing unit tests will not imply production readiness.

## Research-only signed identity verification

Added `paper_identity.py` with a deterministic HMAC-SHA256 verifier for
short-lived, server-issued test tokens. It verifies signature, exact claim
shape, issuer, audience, subject, issued-at, expiry and a 15-minute maximum
lifetime. Tests cover forged signatures, expired/not-yet-valid tokens,
wrong issuer/audience, weak keys and malformed subjects. The test token
issuer is **not** an HTTP login service.

Do not expose `issue_test_token` to website users. No secret is committed;
production keys must be injected server-side and rotated. This verifier has
no revocation list, session store, multi-key rotation or browser protections.
`VerifiedPrincipal` can still be constructed by trusted Python code, so
actual enforcement requires an HTTP boundary that invokes verification on
every request and never accepts principal objects from client input.
