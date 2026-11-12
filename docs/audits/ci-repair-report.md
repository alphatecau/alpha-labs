# CI repair report — 2026-11-12

Status: VERIFIED locally against main `b973e4330888970184cf9f90fb9487a1ff563b3b`.
Final research head and exact-head workflow evidence are recorded in the draft PR.
No merges, deployed configuration, credentials or production systems changed.

## Priority reconciliation

- #97 `194a4a340b2ff0f4e5278125b0e30553a747ceb4`: current CI is green,
  but its later commit narrowed Ruff from E4/E7/E9/F63/F7/F82 to E9/F63/F7/F82.
  Reused its actual backend, CodeQL, Gitleaks and Dependabot files on current main.
- #100 `a903ca6b3c5772302286f175baef5c8bb446df30`: current Ruff run
  [43153779647](https://github.com/alphatecau/alpha-labs/actions/runs/43153779647)
  fails with 124 violations: E701=72, E702=46, E401=3, E741=2, E402=1.
  The temporary ignores do not provide an accepted source repair. This branch
  fixes every reported violation in source and restores all selected rules.
- #99 `09f9c9870d9b2bb9ed77b6cba6aaff6591b0300e`: SUPERSEDED by merged
  #98. The files are not byte-identical, but main already has equivalent unittest
  assertions for valid quotes, stale/future/unsupported inputs and denied unsafe
  simulated orders. All four original #99 methods passed against current main's
  quote implementation. No duplicate patch was applied. Recommend closure only
  after owner review; this task does not close it.
- #92/#94: keep the stronger exact-head and incomplete-evidence implementation in
  #94; it is reconciled in the separate security/integration branch, preserving
  the original drafts and their ancestry.

## Implemented and verified

- Ruff 0.15.22, selected E4/E7/E9/F63/F7/F82, no ignored codes or file exclusions.
  E701/E702 were expanded, imports split/moved, and ambiguous OHLCV locals renamed.
  Eighteen affected source ASTs were equivalent after explicit import normalization
  and the documented local identifier renames; existing behavior tests pass.
- Pytest discovery includes function-style adversarial tests not found by unittest.
  JUnit evidence must contain tests and zero failures/errors/skips; missing evidence
  fails the workflow. Evidence artifacts are uploaded even after failure.
- A runtime dependency audit found known advisory entries in cryptography 46.0.7.
  Pyproject and existing dependency-enabled workflows now require `>=50.0.0,<51`.
  Resolved cryptography 50.0.2, cffi and pycparser pass the fresh strict audit.
- Checkout credentials are not persisted in new/modified workflows. CodeQL's
  security-events write permission is confined to its analysis job. No PR-target
  event executes untrusted code with privileged credentials.
- The pinned Gitleaks 8.24.3 archive is checksum-verified before extraction; no
  privileged installer is needed. A redacted scan found no leaks in the working tree.

## Executed checks

Python 3.12.14, cryptography 50.0.2, Ruff 0.15.22, Node 24.22.1.

| Command | Exit | Evidence |
|---|---:|---|
| `ruff check packages deployment tests` | 0 | All selected rules pass; 124 original findings repaired |
| `PYTHONPATH=packages/alpha_lab/src python -m unittest discover -s tests/unit -p 'test_*.py' -v` | 0 | 234 tests before dependency upgrade |
| `PYTHONPATH=packages/alpha_lab/src python -m pytest -q -ra --strict-markers --strict-config -o addopts='' --junitxml=/tmp/master-ci-junit-secure.xml tests/unit` | 0 | 247 tests plus 48 subtests; zero skipped, on patched dependency |
| `node --test apps/sites/tests/*.test.cjs` | 0 | 36 website tests |
| `PYTHONPATH=packages/alpha_lab/src python -m alpha_lab.cli examples/SYNTHETIC_SOLUSDC_1h.csv --quote USDC --provenance synthetic --output /tmp/master-ci-smoke.json` | 0 | Synthetic input only, no market-performance claim |
| `pip-audit --strict -r /tmp/master-runtime-requirements.txt --format=json` | 0 after repair | Resolved runtime dependencies; no known vulnerabilities |
| `/tmp/gitleaks dir --redact --exit-code 1 --no-banner .` | 0 | No leaks found; archive checksum verified |
| `bandit -q -r packages deployment -ll -f json` | 1 | Two B310 MEDIUM review findings in existing public-data urllib call sites; no HIGH findings |
| `git diff --check` | 0 | No whitespace errors |

Bandit's two call sites use fixed public HTTPS provider origins and validated
market symbols in the inspected callers; these findings are review evidence,
not proof of an exploitable authentication bypass. Redirect/transport hardening
of legacy historical importers remains separate from the new paper-feed boundary.
No Bandit rules were disabled. A passing dependency scan is a time-bound advisory
snapshot, not a security guarantee. CodeQL and exact-head CI require the published
branch run; they are not inferred from local tests.

Rollback: revert this bounded CI/dependency/source-repair commit on its research
branch. The integration branch depends on it. The original main and PRs remain
unchanged until separately authorized review/merge.
