# Alpha Labs — security acceptance review (research branch)

Review date: 2026-11-10. Scope: PR #79 synthetic BFF → signed research API → disposable PostgreSQL 16 integration. **Decision: NO-GO for deployment.**

## Verified CI evidence
- GitHub Actions run 42648546393 passed PostgreSQL 16 isolated RLS fixture, transaction-local context fixture and one end-to-end two-user acceptance test.
- Unit tests for OIDC JWT verification, relay and read-only API passed.
- Offline research and Sites regression workflows passed at commit c2ecf397.

## Security findings and limitations
1. **HIGH — arbitrary SQL can bypass tenant RLS.** Policy reads custom `alpha_labs.owner_id` GUC, which the restricted reader can change via `set_config`. A compromised reader connection executing arbitrary SQL could set another account's owner ID. RLS is defence in depth, not independent tenant authority. Current fixed SQL and parameter binding reduce exposure, but arbitrary SQL must remain impossible through any API.
2. **HIGH — end-to-end test is synthetic, not deployed OIDC.** Tests create local sessions directly, without actual Auth0 authorization-code + PKCE callback, nonce/state handling, cookie issuance/rotation or HTTPS reverse-proxy validation. No production identity-provider integration is verified.
3. **HIGH — production TLS backend transport is injected, not implemented.** The relay expects a trusted backend_get callable; fixed-origin TLS, redirect rejection, timeout and certificate verification remain deployment requirements.
4. **MEDIUM — ownership model is constrained.** Session bridge checks a hard-coded `primary` ownership slot and derives `oidc_ + SHA256(issuer,subject)`; it does not demonstrate an independently provisioned immutable account UUID or multi-account selection policy.
5. **MEDIUM — limited adversarial scope.** The integration test checks two accounts, missing context, revoked ownership and no INSERT grant. It does not establish safety under compromised database credentials, concurrent pooled connections, replay, CSRF, proxy spoofing or failure injection in deployed infrastructure.
6. **HIGH — independent review is outstanding.** This internal code inspection is not an independent penetration test or external sign-off.

## Required before deployment
- Independently review and approve fixed-query DB surface and eliminate any dynamic SQL execution path; if arbitrary SQL is a threat model requirement, redesign tenant enforcement to use database-verifiable tenant authority rather than a caller-settable custom GUC.
- Implement and verify complete Auth0/OIDC browser lifecycle, account ownership mapping, secure session cookies, and trusted proxy boundary.
- Implement and test pinned-origin HTTPS backend transport with timeouts, redirect rejection and no browser credential forwarding.
- Extend disposable PostgreSQL tests to cover concurrent reuse, connection errors, forged account headers, and privilege escalation; document expected residual risk.
- Obtain independent security reviewer sign-off and separate authorisation for merge, staging deployment and GPT Site link.

No staging/production database changes, deployments, merges or trading are authorised by this review.
