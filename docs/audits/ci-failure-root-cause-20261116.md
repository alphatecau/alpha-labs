# Alpha Labs CI failure root-cause audit — 2026-11-16

Baseline: latest observed default-branch commit `c025992ebd6126fb1fa833b81fb3dcac7e75f764`. Historical logs are from 14 November; do not mistake historical failure for current failure.

| Run | Job/first failed step | First actionable cause | Latest source reconciliation |
|---|---|---|---|
| 43651089945 | research / Run independent research tests | `ModuleNotFoundError: No module named 'alpha_lab.research.paper_account_service'` | Module exists at **alpha_lab/research/paper_account_service.py** on baseline. Earlier expected packages/ path was incorrect. Exact-head rerun required. |
| 43651089953 | python / Unit regression suite | Same module import error in `tests/unit/test_isolated_staging_readiness.py`; zero-skipped enforcement also failed downstream | Module exists in current source; exact-head rerun required. runtime-dependencies job passed historically. |
| 43647103651 | auth0-callback / Run Auth0 callback adversarial tests | `ImportError: cannot import name 'rsa' from 'cryptography.hazmat.primitives'` | `deployment/auth0_verified_identity.py` now imports `rsa` from `cryptography.hazmat.primitives.asymmetric`. Exact-head rerun required. |
| 43649874765 | auth0-disposable-recovery / Auth0 session and state recovery acceptance | `TypeError`: lambda takes zero positional arguments but one given (six tests errored) | `tests/integration/test_auth0_disposable_recovery.py` now uses `staticmethod(lambda: psycopg.connect(cls.dsn))`; commit b7aa3ea notes descriptor fix. Disposable PG rerun required. |
| 43647341515 | local-paper (3.12) / Verify local paper and shared dependencies | Ruff E731 lambda assignment in `tests/integration/test_auth0_staging_bootstrap.py` | Current source uses `def factory()` in affected test. Python 3.13 job was cancelled after failed verification and artifact upload also failed; cancellation is not a PASS. |

Evidence: GitHub Actions job logs 132619483857, 132619484099, 132607236159, 132615726110 and 132607965353. Source was fetched through authenticated GitHub connector. No exact-head test execution was completed in this audit. Do not treat source inspection as runtime verification.

Security finding: `docs/security/pr122-preliminary-security-review.md` identifies a HIGH-risk trust-boundary concern: public `VerifiedPrincipal` dataclass can be constructed without proof of OIDC verification. Existing provisioning-authority tests and server-side checks must be assessed before accepting the boundary; do not change auth logic without review.

Recent PR #135 describes a concurrency race where an older successful dual-source paper gate refresh could clear a newer HALT. Prioritise independent review and exact-head regression verification. Do not infer merge or test status from PR title.
