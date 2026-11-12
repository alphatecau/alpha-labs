# Staging evidence matrix · updated 13 November 2026

The current review is recorded in the [engineering acceptance report](master-engineering-completion-20261113.md) and the [machine-readable matrix](independent-staging-acceptance-20261112.json). Each current record includes evidence, environment, tested source and reproducibility. Historical results and source receipts follow the current matrix.

| ID | Area | Status | Source | Environment |
|---|---|---|---|---|
| R01 | Exact heads and dependency ancestry | PASS | c5fd585 | GitHub read-only refs, local Git objects and branch ancestry |
| CI103 | Existing draft CI | PASS | 0c0a99f | GitHub Actions PR-triggered exact-head workflow run |
| U103 | Fresh pinned unit reproduction | PASS | 0c0a99f | Managed Linux, Python 3.12.14, pytest 9.2.0 |
| CI104 | Existing draft CI | PASS | f41e8c7 | GitHub Actions PR-triggered exact-head workflow run |
| U104 | Fresh pinned unit reproduction | PASS | f41e8c7 | Managed Linux, Python 3.12.14, pytest 9.2.0 |
| CI105 | Existing draft CI | PASS | be2901e | GitHub Actions PR-triggered exact-head workflow run |
| U105 | Fresh pinned unit reproduction | PASS | be2901e | Managed Linux, Python 3.12.14, pytest 9.2.0 |
| PG104 | Original security stack PostgreSQL | PASS | f41e8c7 | Managed Linux, Python 3.12.14, pytest 9.2.0, psycopg 3.3.9, disposable loopback PostgreSQL 16.2 |
| PG105 | Original paper integration PostgreSQL | PASS | be2901e | Managed Linux, Python 3.12.14, pytest 9.2.0, psycopg 3.3.9, disposable loopback PostgreSQL 16.2 |
| DEP-OLD | Original dependency constraint | FAIL | 23b463c | Historical exact-source audit, preserved from 12 November 2026 |
| DEP-NEW | Dependency upgrade verification | PASS | c5fd585 | Managed Linux, Python 3.12.14, pytest 9.2.0 |
| AST103 | Ruff repair behavior preservation | PASS | 0c0a99f | Historical exact-source audit, preserved from 12 November 2026 |
| B310-BEFORE | Historical public downloader redirects | FAIL | 58cdc4d | Historical exact-source audit, preserved from 12 November 2026 |
| BANDIT-AFTER | Three medium findings disposition | PASS | c5fd585 | Managed Linux, Python 3.12.14, pytest 9.2.0 |
| CHECKPOINT-BEFORE | Unanchored owner journal rollback | FAIL | 58cdc4d | Historical exact-source audit, preserved from 12 November 2026 |
| CHECKPOINT-REPAIR | Protected checkpoint authority | PASS | c5fd585 | Managed Linux, Python 3.12.14, pytest 9.2.0, psycopg 3.3.9, disposable loopback PostgreSQL 16.2 |
| CHECKPOINT-COMMIT | Commit uncertainty and recovery | PASS | c5fd585 | Managed Linux, Python 3.12.14, pytest 9.2.0, psycopg 3.3.9, disposable loopback PostgreSQL 16.2 |
| DB-SHUTDOWN | Actual database outage | PASS | c5fd585 | Managed Linux, Python 3.12.14, pytest 9.2.0, psycopg 3.3.9, disposable loopback PostgreSQL 16.2 |
| HTTP-RELAY | Authenticated server-side boundary | PASS | c5fd585 | Managed Linux, Python 3.12.14, pytest 9.2.0, psycopg 3.3.9, disposable loopback PostgreSQL 16.2 |
| QUOTAS | Shared quotas and isolation | PASS | c5fd585 | Managed Linux, Python 3.12.14, pytest 9.2.0, psycopg 3.3.9, disposable loopback PostgreSQL 16.2 |
| AUTH0-REAL | Real Auth0 acceptance | BLOCKED | c5fd585 | Real hosted Auth0 unavailable |
| PROXY-REAL | Actual HTTPS reverse proxy | BLOCKED | c5fd585 | Existing Render service is a health probe |
| STORAGE-REAL | Protected storage/key/restore acceptance | BLOCKED | c5fd585 | Hosted storage and key custody unavailable |
| CONTROL-STATE | Full mutable control-state rollback resistance | PASS | c5fd585 | Managed Linux, Python 3.12.14, pytest 9.2.0, psycopg 3.3.9, disposable loopback PostgreSQL 16.2 |
| COINBASE | Quote provenance and freshness | PASS | df81e55 | Managed Linux with actual read-only Coinbase public quotes |
| WEB-LOGIC | Existing website and mobile controller regression | PASS | c5fd585 | Managed Linux, Node 24.22.1 |
| ANDROID | Android/browser acceptance | BLOCKED | c5fd585 | Managed Linux, Chromium 156 and Playwright 1.62 |
| SITE-ACCESS | Existing hosted Site owner-only gate | FAIL | 53f9773 | Sites deployment metadata and anonymous HTTPS probe from managed Linux |
| SITE-VERSIONS | Saved/publication provenance | PASS | 53f9773 | Sites deployment metadata and anonymous HTTPS probe from managed Linux |
| SITE-SOURCE | Hosted saved source inspection | BLOCKED | 53f9773 | Sites deployment metadata and anonymous HTTPS probe from managed Linux |
| SITE-RELAY | Hosted paper relay acceptance | BLOCKED | c5fd585 | Sites deployment metadata and anonymous HTTPS probe from managed Linux |
| PR99 | Superseded quote-test repair | PASS | 09f9c98 | Historical exact-source audit, preserved from 12 November 2026 |
| PR92 | Original collector negative reproduction | FAIL | 6f5250b | Historical exact-source audit, preserved from 12 November 2026 |
| LOCAL-REPAIR | Repair regression execution | PASS | df81e55 | Managed Linux, Python 3.12.14, pytest 9.2.0 |
| MAKE | Documented unittest entry point | PASS | df81e55 | Managed Linux, Python 3.12.14, pytest 9.2.0 |
| HISTORY | Exhaustive historical review | NOT_INSPECTED | c5fd585 | GitHub read-only refs, local Git objects and branch ancestry |
| CI-REPAIR | Executed repair-head CI | PASS | e045f26 | Historical exact-source audit, preserved from 12 November 2026 |

## Historical review · 12 November 2026

# Independent review and staging acceptance — 2026-11-12

**NO-GO for staging and production.** Priority defects repaired on an isolated research branch; external acceptance remains incomplete. Main and existing hosted Site are unchanged. No merge, deployment, access/credential change, real-money order or reserved 2027 holdout access occurred.

Review method: freshly fetched exact code, newly executed tests, decoded CI checkout logs, tree-hash comparisons and negative reproductions. Prior reports were not treated as evidence. This is automated engineering review, not independent human sign-off.

## Dependency review

| PR | Exact reviewed head | Fresh unit tests | Fresh PostgreSQL tests | Existing CI |
|---|---|---|---|---|
| #103 | `0c0a99f62f8e25df6c66a74ea8447922f57ea16d` | 247 + 48 subtests | Not applicable to its diff | 12 successful runs |
| #104 | `f41e8c7ee43575d50771ddc4cfe96389c468243e` | 460 + 207 subtests | 35 passed | 16 successful runs |
| #105 | `58cdc4df30004df424b2ad9da7f5905321fadf63` | 518 + 230 subtests | 38 passed | 20 successful runs |

Main: `b973e4330888970184cf9f90fb9487a1ff563b3b`. Dependency ancestry and dry conflict inspection passed in this order. #103 checkout `4fc809b4d59ae71f25203a63ec71b51fbbcb9752` has exactly the head tree `a68fbd5c3fa9606839ab4ce8a1ac307f854bb3b6`; #104 checkout `64aaa747c4c6923caed8b896369f48ef30b66bc5` has exactly the head tree `734a32a9babeabb99b4f70ad851d832460b01c6c`. #105 checks out its head directly.

## Traceable matrix

PASS = executed/observed scope; FAIL = reproduced defect/unmet gate; BLOCKED = unavailable external evidence; NOT_INSPECTED = no complete examination. A PASS elsewhere never overrides a FAIL or BLOCKED acceptance gate. Machine-readable details: [JSON](independent-staging-acceptance-20261112.json).

| ID | Area | Status | Evidence |
|---|---|---|---|
| R01 | Exact heads and dependency ancestry | **PASS** | [dependency-review.json](evidence/independent-review-20261112/dependency-review.json) |
| CI103 | Existing draft CI | **PASS** | [ci-snapshot.json](evidence/independent-review-20261112/ci-snapshot.json), [checkout-tree-proof.json](evidence/independent-review-20261112/checkout-tree-proof.json) |
| U103 | Fresh pinned unit reproduction | **PASS** | [unit-103.log](evidence/independent-review-20261112/unit-103.log) |
| CI104 | Existing draft CI | **PASS** | [ci-snapshot.json](evidence/independent-review-20261112/ci-snapshot.json), [checkout-tree-proof.json](evidence/independent-review-20261112/checkout-tree-proof.json) |
| U104 | Fresh pinned unit reproduction | **PASS** | [unit-104.log](evidence/independent-review-20261112/unit-104.log) |
| CI105 | Existing draft CI | **PASS** | [ci-snapshot.json](evidence/independent-review-20261112/ci-snapshot.json), [checkout-tree-proof.json](evidence/independent-review-20261112/checkout-tree-proof.json) |
| U105 | Fresh pinned unit reproduction | **PASS** | [unit-105.log](evidence/independent-review-20261112/unit-105.log) |
| PG104 | Original security stack PostgreSQL | **PASS** | [postgres-104.log](evidence/independent-review-20261112/postgres-104.log) |
| PG105 | Original paper integration PostgreSQL | **PASS** | [postgres-105.log](evidence/independent-review-20261112/postgres-105.log) |
| DEP-OLD | Original dependency constraint | **FAIL** | [dependency-audit.json](evidence/independent-review-20261112/dependency-audit.json) |
| DEP-NEW | Dependency upgrade verification | **PASS** | [dependency-audit.json](evidence/independent-review-20261112/dependency-audit.json) |
| AST103 | Ruff repair behavior preservation | **PASS** | [ast-equivalence.json](evidence/independent-review-20261112/ast-equivalence.json) |
| B310-BEFORE | Historical public downloader redirects | **FAIL** | [negative-reproductions.json](evidence/independent-review-20261112/negative-reproductions.json), [bandit-disposition.json](evidence/independent-review-20261112/bandit-disposition.json) |
| BANDIT-AFTER | Three medium findings disposition | **PASS** | [bandit-disposition.json](evidence/independent-review-20261112/bandit-disposition.json), [repair-source-fingerprint.json](evidence/independent-review-20261112/repair-source-fingerprint.json) |
| CHECKPOINT-BEFORE | Unanchored owner journal rollback | **FAIL** | [negative-reproductions.json](evidence/independent-review-20261112/negative-reproductions.json) |
| CHECKPOINT-REPAIR | Protected checkpoint authority | **PASS** | [postgres-repair.log](evidence/independent-review-20261112/postgres-repair.log), [unit-repair.log](evidence/independent-review-20261112/unit-repair.log), [repair-source-fingerprint.json](evidence/independent-review-20261112/repair-source-fingerprint.json) |
| CHECKPOINT-COMMIT | Commit uncertainty and recovery | **PASS** | [postgres-repair.log](evidence/independent-review-20261112/postgres-repair.log), [unit-repair.log](evidence/independent-review-20261112/unit-repair.log) |
| DB-SHUTDOWN | Actual database outage | **PASS** | [database-shutdown.json](evidence/independent-review-20261112/database-shutdown.json) |
| HTTP-RELAY | Authenticated server-side boundary | **PASS** | [postgres-repair.log](evidence/independent-review-20261112/postgres-repair.log) |
| QUOTAS | Shared quotas and isolation | **PASS** | [postgres-repair.log](evidence/independent-review-20261112/postgres-repair.log) |
| AUTH0-REAL | Real Auth0 acceptance | **BLOCKED** | See detailed JSON / limitations |
| PROXY-REAL | Actual HTTPS reverse proxy | **BLOCKED** | See detailed JSON / limitations |
| STORAGE-REAL | Protected storage/key/restore acceptance | **BLOCKED** | See detailed JSON / limitations |
| CONTROL-STATE | Full mutable control-state rollback resistance | **NOT_INSPECTED** | See detailed JSON / limitations |
| COINBASE | Quote provenance and freshness | **PASS** | [coinbase-observation.json](evidence/independent-review-20261112/coinbase-observation.json) |
| WEB-LOGIC | Existing website and mobile controller regression | **PASS** | [website.log](evidence/independent-review-20261112/website.log) |
| ANDROID | Android/browser acceptance | **BLOCKED** | See detailed JSON / limitations |
| SITE-ACCESS | Existing hosted Site owner-only gate | **FAIL** | [site-metadata.json](evidence/independent-review-20261112/site-metadata.json) |
| SITE-VERSIONS | Saved/publication provenance | **PASS** | [site-metadata.json](evidence/independent-review-20261112/site-metadata.json) |
| SITE-SOURCE | Hosted saved source inspection | **BLOCKED** | [site-metadata.json](evidence/independent-review-20261112/site-metadata.json) |
| SITE-RELAY | Hosted paper relay acceptance | **BLOCKED** | [site-metadata.json](evidence/independent-review-20261112/site-metadata.json) |
| PR99 | Superseded quote-test repair | **PASS** | [pr99-main-equivalence.log](evidence/independent-review-20261112/pr99-main-equivalence.log) |
| PR92 | Original collector negative reproduction | **FAIL** | See detailed JSON / limitations |
| LOCAL-REPAIR | Repair regression execution | **PASS** | [unit-repair.log](evidence/independent-review-20261112/unit-repair.log), [postgres-repair.log](evidence/independent-review-20261112/postgres-repair.log), [website.log](evidence/independent-review-20261112/website.log), [repair-source-fingerprint.json](evidence/independent-review-20261112/repair-source-fingerprint.json) |
| MAKE | Documented unittest entry point | **PASS** | [make-research-test-summary.log](evidence/independent-review-20261112/make-research-test-summary.log) |
| HISTORY | Exhaustive historical review | **NOT_INSPECTED** | See detailed JSON / limitations |

## Repairs and security limits

1. Reproduced both downloader redirects using actual urllib processing and synthetic responses. Replaced implicit redirects with bounded fixed-origin HTTPS GETs; added oversize/status/origin/timeout and valid-JSON-prefix regressions. The local diagnostic probe binds loopback. All three existing Bandit medium findings are resolved without suppressions, and a separate CI job enforces zero medium/high findings.
2. Reproduced loss of a committed fill followed by successful re-arm after deleting the unanchored journal. Added an independently signed, append-only, single-owner PostgreSQL checkpoint authority with role/owner/permission checks. The browser BFF refuses an offline/unprotected session. Existing journal, ledger and risk engine are reused.
3. Checkpoint persistence and SQLite fill persistence are separate transactions. If the local fill commits but the authority cannot confirm it, the API returns 503/HALT and refuses automatic adoption on restart. Independent operator reconciliation is required; no silent privileged fallback or duplicate fill. Normal checkpointed restart and same-ID recovery pass.
4. This protects the fill-event journal only. It does not certify all mutable paper_guard metadata against malicious rollback, coordinated rollback of both authorities, whole-host compromise, real key custody or the future deployment. One owner and one paper writer process remain mandatory.

## Executed commands

Python executable `/tmp/alpha-audit-venv/bin/python` (3.12.14), cryptography 50.0.2, Bandit 1.9.4. Prefix `PYTHONPATH=packages/alpha_lab/src:.:tests/integration` for Python test commands. Baseline commands ran in their own pinned worktrees. All commands below exited 0 except explicit negative baselines. Raw logs and environment-safe summaries are committed in the evidence directory.

```sh
python -m pytest tests/unit -q --junitxml=/tmp/independent-103-unit.xml
python -m pytest tests/unit -q --junitxml=/tmp/independent-104-unit.xml
python -m pytest tests/unit -q --junitxml=/tmp/independent-105-unit.xml
python -m pytest tests/unit -q --junitxml=/tmp/independent-repair-unit.xml
ALPHA_DISPOSABLE_PG_CI=1 ALPHA_TEST_PG_DSN=postgresql://postgres:ci-only@127.0.0.1:5432/alpha_rls_test ALPHA_TEST_POSTGRES_DSN=postgresql://alpha_test:local_ci_only@127.0.0.1:5432/alpha_security_test python -m unittest discover -s tests/integration -p 'test_*.py' -v
make research-test  # venv selected in PATH; exact unit command is in Makefile
node --test apps/sites/tests/*.test.cjs
python -m alpha_lab.cli examples/SYNTHETIC_SOLUSDC_1h.csv --quote USDC --provenance synthetic --output /tmp/independent-smoke.json
ruff check packages deployment tests scripts/engineering_status.py scripts/reconcile_repository.py
/tmp/actionlint -shellcheck='' -pyflakes=''
/tmp/gitleaks dir --redact --exit-code 1 --no-banner .
bandit -q -r packages deployment -ll -f json -o /tmp/independent-bandit-after.json
pip-audit --strict -r /tmp/independent-current-runtime.txt --format json
git diff --check
```

The PostgreSQL command ran separately at #104, #105 and the repair tree: respectively 35, 38 and 44 tests, no skips. All credentials in that command are synthetic disposable fixture values. Three supplied SQL fixtures also passed via psql -v ON_ERROR_STOP=1. The labelled owned database was then deliberately stopped/removed for the real outage test; CHECKPOINT_HALT/503 and zero fills were observed. No production database was contacted.

Negative command `pip-audit --strict -r /tmp/independent-old-runtime.txt --format json` (file content cryptography>=44,<47) exited 1 with seven advisory entries/four distinct IDs for 46.0.7. Before-repair Bandit exited 1 with three medium findings; after-repair Bandit exits 0. Original #92 adversarial failures are expected negative evidence. A development test initially emitted a runpy import warning; it was removed by calling the probe main function directly, and the full unit suite reran cleanly.

## Hosted Site and unavailable acceptance

Read-only native Sites metadata confirms the existing research Site is public (policy revision 2). Latest saved version is 4; latest recorded successful publication is version 2, not confirmed version 4. The unauthenticated paper-state GET returned research HTML identical to the root. No private paper-state JSON was observed at that path; this is not proof of other route isolation or owner identity acceptance. Two saved archive downloads could not be authorized/resolved; source-write credentials, bypass tokens and runtime-secret reads were not requested. The Site was not modified.

Real Auth0 tenant/client/callback test identity, actual TLS proxy peer configuration, protected checkpoint host/key/backup bindings and physical Android acceptance are unavailable. Environment status has no configured secrets/runtime bindings. These are BLOCKED, not mock-based passes.

Managed browser QA is BLOCKED under [Sites SKILL.md](skill://plugin_connector_1p_689987207de08191979cf68eca2941c6/sites/SKILL.md): “If `cua_repl.js` is unavailable, skip browser QA: do not start a preview server, install a browser, or improvise another browser-control path.” No such tool is exposed. The loopback HTTP integration test is a backend protocol test, not a preview/browser test.

## Reconciliation after dependency review

#99 is assertion-equivalent to merged #98/main: four original methods rerun against the exact main quote module pass. #92 alone remains defective and is superseded by #94 retained in #104/#105. #97/#100 repair intent is covered by #103, with the original #100 failing head left accurately recorded. Recommend closure only after owner review; do not close or merge automatically. The reviewed #103/#104/#105 heads are conflict-free against current main and their declared bases; do not infer that every historical branch is reconciled.

Review order remains #103 → #104 → #105 → this separate hardening draft. All baseline reports and research evidence remain intact. Exact repair commit and new CI URLs are added to the draft PR after publication; old-head CI is never used to certify a changed repair head.

## Acceptance decision

- Offline tested research: GO within the recorded scope.
- Private paper staging: NO-GO until real identity/proxy, storage/restore, hosted owner boundary, control-state integrity and device acceptance are independently satisfied.
- Public paper deployment: NO-GO; no deployment or access change authorized.
- Real money: NO-GO; prohibited and no broker execution path added.

Owner-controlled acceptance requires a separately authorized isolated environment and approved identity/ingress/storage/key bindings. No approval to create those resources or change existing access is implied by these draft repairs.

## Repair-head CI receipt

Draft [#106](https://github.com/alphatecau/alpha-labs/pull/106) source head `e045f26994078a3193b113a6aa73af8e0f5e5d0a` passed all nine observed workflow runs. Decoded checkout logs confirm that exact SHA. [Backend 43199233257](https://github.com/alphatecau/alpha-labs/actions/runs/43199233257): 525 passed + 230 subtests, 755 JUnit cases, zero skips/errors/failures, and no known runtime dependency vulnerabilities. [Owner acceptance 43199233254](https://github.com/alphatecau/alpha-labs/actions/runs/43199233254): 26 tests + two subtests, five public-transport tests and the separate Bandit medium/high gate all passed. [CodeQL 43199233016](https://github.com/alphatecau/alpha-labs/actions/runs/43199233016) and the remaining triggered workflows succeeded.

The matrix now contains 37 rows: 24 PASS, five FAIL baseline/unmet-gate records, six BLOCKED and two NOT_INSPECTED. These are scoped evidence records, not 37 deployment gates. No current unit/integration test failed. The concluding audit commit adds this receipt without changing application source; its current exact-head CI is recorded separately in the draft PR. The NO-GO decisions remain unchanged.
