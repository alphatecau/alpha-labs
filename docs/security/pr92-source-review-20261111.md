# PR #92 source review and adversarial reproduction

Research-only review of actual PR head `6f5250b82a8242f58bfbe564c527dd233d965b8e`,
based on main `aa1634e8fd4c6987b9ac4c2e89e10b907c119944`.
This is a fresh source/test/log re-audit by the same assistant, not independent
human approval or a production security certification. No merge or deploy.

## Acceptance findings

The original 27 collector tests passed locally. Fresh GitHub reads confirmed
the five successful workflow runs on that exact head, and decoded audit log
[43114343388](https://github.com/alphatecau/alpha-labs/actions/runs/43114343388)
reported 63/63 observed PR heads with evidence and the actual failures on #42/#76.

The exact failing heads remain #42 `7130307c0d20df0309b8df1883182111a76bdb4a`
and #76 `529c21baf97acbad60dddb11e1c5d3f84c385662`. Independently decoded
[42541378983](https://github.com/alphatecau/alpha-labs/actions/runs/42541378983)
contains three HALT-message assertion failures; decoded
[42639164939](https://github.com/alphatecau/alpha-labs/actions/runs/42639164939)
contains a missing-cryptography import failure. Open successor #77 addresses
the latter dependency; this review does not change those PRs.

Verified medium-severity defects repaired on
`research/pr92-independent-hardening-20261111`:

1. `http.client.IncompleteRead` escaped collection and could prevent the partial
   artifact from being written. Catch HTTP protocol/read errors and sanitize them.
2. Inconsistent total counts and invalid/missing completed-run conclusions could
   be accepted as complete evidence. Reject contradictory or invalid run data.
3. Main/PR heads were read once and could change before collection completed.
   Revalidate the complete paginated inventory and main; changes or failed
   revalidation retain the original evidence but mark collection incomplete.

Six new adversarial test methods were run against the original source: FAIL
(11 assertion failures and 2 errors across subcases), confirming the gaps.
After repair, all 33 collector tests pass. Pagination, response bounds, GET-only
fixed-origin requests, redirect rejection, read-only token permissions and
nonzero incomplete collection remain intact. Rate-limit denials stop collection
without retrying or bypassing the limit; partial evidence is retained. The
collector does not return an aggregate CI PASS or claim external-check coverage.

## Local evidence

Environment: Python 3.12.14, cryptography 46.0.7, Node 24.22.1.
Each command below exited 0 on the repaired tree; final commit and CI URLs are
recorded in the accompanying draft PR.

```sh
PYTHONPATH=packages/alpha_lab/src /tmp/alpha-audit-venv/bin/python -m unittest discover -s tests/unit -p test_engineering_status.py -v
PYTHONPATH=packages/alpha_lab/src /tmp/alpha-audit-venv/bin/python -m unittest discover -s tests/unit -p 'test_*.py' -v
node --test apps/sites/tests/*.test.cjs
PYTHONPATH=packages/alpha_lab/src /tmp/alpha-audit-venv/bin/python -m alpha_lab.cli examples/SYNTHETIC_SOLUSDC_1h.csv --quote USDC --provenance synthetic --output /tmp/pr92-synthetic-smoke.json
git diff --check
```

Results: 33 targeted tests, 260 full Python tests, 36 website tests and synthetic
smoke passed. The live read-only audit is also wired to this branch's PR CI.
Retrieval completeness never means that other PRs' CI passes. This is not an
atomic repository snapshot; refs can change after the final observation.

## Prioritized security work outside this repair

- HIGH: PR #84's BFF continues reading after ownership revocation. Independently
  reproduced with the real SQLite registry confirming revocation. A separate
  `research/auth-ownership-revocation-20261111` repair checks authorization before
  each read, with real disposable PostgreSQL regression coverage.
- HIGH, threat-model dependent: legacy shared-role RLS trusts a caller-settable
  tenant GUC. A real PostgreSQL test reproduces tenant selection by that role.
  The existing distinct-role implementation passes arbitrary-SQL isolation tests;
  the legacy adapter must not claim the same boundary.
- Remaining: newest BFF lacks the shared limiter present in the older paper-status
  chain; actual Auth0 browser acceptance, real proxy topology, production role
  provisioning, and independent human review remain unverified.

Task: exact-head audit hardening; owned files are the collector, its tests and
this report. Dependency is PR #92, not main integration. Budget approximately
90 minutes across this audit and the separate auth/DB work. Rollback: revert the
isolated commit. Stop on conflicts, unavailable authorized access, production
dependencies, credentials or budget exhaustion. No new secrets, external database
connections, production changes, trading or reserved 2027 dataset access.
