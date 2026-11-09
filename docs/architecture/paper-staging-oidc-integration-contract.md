# Identity provider integration contract — research staging

## Decision
Do not expose the prototype HMAC verifier to public users. Select an
established OIDC provider before production-facing authentication. The
provider must supply a stable issuer, audience-bound access tokens, rotating
JWKS, and an independently verifiable user identity. Do not accept an ID
token as an API access token unless its audience and intended use are
explicitly correct.

## Required server-side boundary
1. Validate JWT signature against pinned provider JWKS and permitted algorithm.
2. Validate exact issuer, audience, expiry, not-before, issued-at, and stable
   subject. Reject unsigned, unknown-key, expired and malformed tokens.
3. Cache JWKS with bounded TTL and controlled refresh; fail closed on
   unresolvable keys or provider outage. Provide key-rotation tests.
4. Map verified (issuer, subject) to persistent, active server-side account
   grants; never accept subject, account ownership or trading authority from
   browser headers, query strings or request bodies.
5. Provide authenticated read-only status only. Enforce rate limits, TLS,
   no-store responses and safe audit logs without tokens or personal data.
6. Run multi-user isolation, revocation, key rotation, replay and browser
   origin tests against actual HTTPS staging before website connection.

## Configuration required from operator
- Chosen OIDC provider and issuer URL.
- API audience identifier and permitted signing algorithms.
- Trusted user onboarding and revocation policy.
- Secret management, backup and operational ownership.

## Current status
Design contract only. No provider selected, no OIDC middleware installed,
no secrets changed, no Render service created. HMAC test verifier remains
research-only. Live trading remains disabled. Release gate: NO-GO.
