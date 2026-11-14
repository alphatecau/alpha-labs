# Alpha Labs — Security release evidence

Candidate: PR #122, restricted-role PostgreSQL and authenticated BFF.
Evidence baseline commit: `45079e442c45a005ee3bc47054c80f17b61e16e2`.

## Automated baseline (historical exact commit)
GitHub Actions runs on the baseline commit completed successfully:
- CodeQL baseline: 43641386530
- Gitleaks secret scan: 43641386567
- Two-account disposable PostgreSQL: 43641386598
- Full authenticated BFF/PostgreSQL tenant acceptance: 43641386541
- Disposable PostgreSQL 16 tenant isolation: 43641386578
- Authenticated integration dependency audit: 43641386579
- Restricted-role synthetic gate: 43641386607
- Backend CI: 43641386611
- Ruff: 43641386623
- Offline research tests: 43641386480
- Sites tests: 43641386638
- Free local paper terminal acceptance: 43641386455

These results do not transfer to later commits. Verify the final PR head separately.
Automated workflows are not a substitute for independent review.

## Outstanding security gates
- AUTH0_REAL_BROWSER: NOT VERIFIED
- Independent human review of OIDC identity trust boundary, reconstructed principal, ownership provisioning and revocation, PostgreSQL role permissions, ingress, replay and concurrency: pending
- External staging ingress and production infrastructure acceptance: not verified
- Branch protection / required reviewer configuration: not confirmed
- No live trading, real-money execution or production deployment authorised

INDEPENDENT_REVIEW: PENDING
PRODUCTION_RELEASE: NO-GO

## Release criteria
1. All security workflows succeed at the exact final head SHA with no security-test skips.
2. Independently test real Auth0 PKCE, state, nonce, cookies, revocation and proxy trust.
3. Review two-account database roles and privilege drift; test concurrent sessions and quota isolation.
4. Resolve critical/high findings; record written reviewer approval and accepted residual risks.
5. Require separate owner authorisation for merge and deployment.

A green automated evidence gate means only that the documented safeguards and workflows exist; it is not a production readiness approval.
