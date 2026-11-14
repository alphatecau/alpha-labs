# Authentication and tenant-isolation acceptance — 2026-11-15

Status: NO-GO. This is an evidence plan, not a claim that tests passed.

## Scope and source of truth
- Reconcile existing PRs #58–#64, #68–#74, #79, #82–#87, #93, #95, #96, #97, #109 before cherry-picking any changes.
- Prefer smallest independently reviewable existing changes. No duplicate implementation or new third-party security skills.
- Record exact base/head SHA, workflow URL, test environment, result, reviewer, and outstanding issue for each gate.
- Keep main, production, secrets, brokers, databases, website and reserved 2027 holdout untouched.

## Acceptance matrix
| ID | Required test | Pass evidence |
| --- | --- | --- |
| AUTH-01 | Invalid signature, algorithm confusion, issuer/audience/azp, expired/nbf/iat, duplicate JSON, JWKS rotation/outage | Negative tests and exact-head CI |
| AUTH-02 | Browser PKCE/state/nonce, callback origin, CSRF, cookie flags, logout/revocation, expiry and concurrent callback | Synthetic tests plus real disposable Auth0 staging |
| INGRESS-01 | Socket-peer trust, spoofed Forwarded/X-Forwarded headers, Host and HTTPS canonicalisation | Negative tests plus observed Render ingress topology |
| TENANT-01 | Two disposable accounts; cross-account SELECT/UPDATE/DELETE and enumeration denied | Real PostgreSQL RLS integration with independent DB roles |
| TENANT-02 | Missing/forged app.account_id, rollback, pooled connection reuse, concurrent transactions | Fail-closed tests, database logs and RLS policy inspection |
| TENANT-03 | Ownership revocation mid-session, quota concurrency, outage and fail-closed read paths | Real DB integration and repeatable concurrency tests |
| API-01 | Unauthenticated reads, forbidden mutations, rate limits, replay and order routes denied | HTTP integration tests |
| CI-01 | No skipped security tests, verified JUnit counts, dependency audit, CodeQL, secret scan and baseline tests | Exact-commit GitHub Actions URLs and artifacts |
| STAGE-01 | Complete real Auth0 + PostgreSQL disposable staging run | Signed-off evidence from independent reviewer |

## Safe sequence
1. Inspect PR ancestry and latest heads; identify already merged, overlapping, superseded and conflicting changes.
2. Review OIDC and proxy primitives independently, then run synthetic negative tests.
3. Review PostgreSQL schema, RLS policies, connection pooling and identity binding.
4. Execute tests only in isolated disposable environments with synthetic identities and orders; never production credentials.
5. Run exact-head CI and collect immutable evidence. Do not infer pass from historical CI.
6. Require independent reviewer sign-off; merge/deploy only after separate owner approval.

## Stop conditions
Any missing real staging resources, incomplete evidence, failing or skipped critical test, unknown proxy topology, unclear tenant isolation, cross-tenant access, or unexpected execution capability means NO-GO. No bypasses.

## Verification record
- Branch creation: recorded separately in GitHub.
- Tests executed in this change: NONE.
- Staging tests executed: NONE.
- Production changes: NONE.
- Release decision: NO-GO.
