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

## Provider selection — dedicated Alpha Labs identity

**Decision:** Establish a separate managed Auth0 tenant/application and API
for Alpha Labs, independent of Q3HASH and AiTec Australia. No tenant or
credentials have been created by this commit.

- Register a dedicated confidential server-side integration and an API
  audience for the paper-status service; configure the exact issuer and
  RS256 JWKS validation. Do not use browser-held client secrets.
- Use the provider's hosted login and standards-compliant authorization-code
  flow with PKCE where the website platform supports it. Confirm GPT Sites
  authentication integration capabilities before implementing browser login.
- Backend must verify access-token issuer, audience, signature, expiry and
  subject on every request; derive ownership exclusively from verified claims
  and persistent grants. Reject ID tokens used as API bearer tokens.
- Add dedicated staging and production application registrations, explicit
  redirect/logout URI allowlists, MFA policy and administrative recovery.
- Avoid enabling open public signup until identity, abuse controls and
  onboarding are tested. Keep paper execution and broker integration disabled.
- Provision the tenant and secrets manually or with separate explicit
  authorisation. Never store Auth0 secrets in GitHub, Render blueprints or Sites.

**Status:** provider selected; actual Auth0 tenant, OIDC middleware, JWKS
rotation and HTTPS end-to-end tests not yet implemented or verified.
