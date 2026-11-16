# CI repair verification ledger — 2026-11-16

## Baseline and evidence provenance
- Repository: https://github.com/alphatecau/alpha-labs
- Default branch: `main`
- Most recent commit returned by GitHub commit search: `c025992ebd6126fb1fa833b81fb3dcac7e75f764`
- Historical workflow job logs inspected: 132619483857, 132619484099, 132607236159, 132615726110, 132607965353.
- Exact-head workflow query for baseline returned no PR-triggered workflow runs. **This endpoint filters to pull-request-triggered runs and is not evidence that no push runs exist.**

## Source-level checks completed
- Correct `rsa` import observed in `deployment/auth0_verified_identity.py`.
- `staticmethod` connection factory observed in `tests/integration/test_auth0_disposable_recovery.py`.
- `def factory` observed in `tests/integration/test_auth0_staging_bootstrap.py`.
- `alpha_lab/research/paper_account_service.py` exists and defines `VerifiedPrincipal`.

## Execution status
No new Ruff, Bandit, dependency-audit, Python 3.12/3.13, disposable PostgreSQL, Android or hosted tests were executed. Local environment cannot resolve github.com to clone repository; connector supports source inspection and GitHub edits but not local test execution. Historical passing checks must not be represented as exact-head PASS.

## Rerun conditions
Run all relevant GitHub Actions workflows on a review branch containing the current baseline, collect run URLs and artifact hashes, require nonzero discovered tests and zero unexpected skips. Use only disposable PostgreSQL service containers for destructive integration tests. Inspect complete logs and failed artifact uploads independently. Record Python versions, exact SHA, commands, pass/fail/skip counts, and environment before upgrading readiness.
