# Alpha Labs — Security release evidence

Candidate: PR #122, restricted-role PostgreSQL and authenticated BFF.
Evidence baseline commit: `45079e442c45a005ee3bc47054c80f17b61e16e2`.

## Exact-main automated verification — 16 November 2026

Verified repository main SHA: `f4e7e01dd3a7d7295b5168515f4e45b7f2ae4c8b`.
Manually dispatched GitHub Actions completed successfully at this exact SHA:
- Auth0 callback adversarial CI: [run 43811035929](https://github.com/alphatecau/alpha-labs/actions/runs/43811035929)
- Authenticated BFF + disposable PostgreSQL integration: [run 43811040000](https://github.com/alphatecau/alpha-labs/actions/runs/43811040000)
- Real tenant RLS with disposable PostgreSQL 16: [run 43811043922](https://github.com/alphatecau/alpha-labs/actions/runs/43811043922)
- Security release evidence gate: [run 43811047994](https://github.com/alphatecau/alpha-labs/actions/runs/43811047994)

Each run was reported completed/success with successful job steps. These are synthetic/adversarial and disposable-database CI checks; they do not prove real Auth0 browser flows, Render ingress trust, production role security or independent reviewer approval. The security release evidence gate checks required workflow-file presence and explicit restriction markers; it does not independently certify release readiness. The historical PR #122 baseline below is retained for audit continuity. See [acceptance issue #154](https://github.com/alphatecau/alpha-labs/issues/154).

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
