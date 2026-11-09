# Day 1 CI stabilisation — evidence and blockers

Audit date: 2026-11-09 (Australia/Brisbane). Research-only. No merge, deployment, credentials, or trading changes.

## Candidate baseline
Latest repository commit returned by GitHub commit search: `2cb66a8ddfc2d2b64246ab9441d0a26a364f7360` (duplicate fill IDs and unsupported fee currencies, #46). This search result is not an independent branch-head attestation.

## GitHub Actions evidence
- https://github.com/alphatecau/alpha-labs/actions/runs/42465262149 — research job 128683205328: 176 tests, one failure.
- https://github.com/alphatecau/alpha-labs/actions/runs/42465255398 — research job 128683180136: 174 tests, one failure.
- Both fail `test_breakout_risk_replay.RiskReplayTests.test_no_signal_has_no_orders_and_reconciles` at line 28: string `'10000.00000000'` versus `'10000'`.
- This is a serialisation/representation mismatch in the assertion, not by itself proof of incorrect arithmetic. Numeric Decimal comparison is a candidate correction, but should only be applied after locating the relevant historical branch and checking the output contract.
- Workflow emits Node 20 deprecation warning for checkout@v4 and setup-python@v5; not the observed failure cause.

## Current verification limitations
- Default-branch lookup of `tests/unit/test_breakout_risk_replay.py` returned 404. Historical failing file cannot be patched safely without identifying its original ref.
- Default-branch lookup of `.github/workflows/research.yml` returned 404; actual workflow path not yet established.
- Commit workflow-run lookup for `2cb66a8...` returned no pull-request-triggered runs (connector endpoint is PR-filtered); combined commit statuses returned empty. Neither result proves success or failure.
- No full current-main test suite was run in this audit. No passing-CI certification.
- Branch inventory was paginated; the first page returned 54 branch names and a continuation cursor, so inventory is not exhaustive.
- Open PR search returned numerous concurrent draft security, accounting, paper-simulator, and data-foundation PRs; independently verify each head SHA, required checks and base before integration.

## Next steps
1. Identify exact failing historical run head refs, locate file and workflow on those refs, and determine whether the failure is already fixed.
2. If still reproducible, change only the test to compare Decimal values after confirming formatting is not the required contract; add a serialisation contract test if necessary.
3. Execute full offline unittest discovery, cryptography-enabled no-skips suite, risk/promotion adversarial tests and website tests on a single pinned candidate SHA.
4. Record per-job links, exit status, test counts, skipped tests, environment, dependency versions, and SHA.
5. Require all mandated checks green or explicitly document NO-GO blockers. Do not merge or deploy.

## Gate
**BLOCKED / UNVERIFIED**. Historic failures are confirmed, but current candidate CI and full tests are not established.
