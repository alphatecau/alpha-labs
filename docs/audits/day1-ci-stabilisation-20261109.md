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

## Follow-up verification — 2026-11-09
- Run 42465262149 checked out `research/strategy-evidence-gates-v1` at `1afceec5f326850ccb957d0df1d468d2b2aff179` (confirmed from job log).
- Run 42465255398 checked out the same branch at `b4dc55a541b979abd23781804bb01bce1bdef09b` (confirmed from job log).
- Historical test located at `tests/unit/test_breakout_risk_replay.py` on `1afceec5...`; its literal string assertion was the observed failure.
- Created isolated fix branch `fix/day1-breakout-decimal-assertion-20261109` from the failing commit and changed only the assertion to `self.assertEqual(Decimal(report["final_liquidatable_value"]), Decimal("10000"))`.
- Patch commit: `b877d92c3faabaaf9fb24888195c9dc9f8eddeff`; read-back confirmed modified file.
- Draft fix PR: https://github.com/alphatecau/alpha-labs/pull/51 (targets the historical research branch, not main).
- Fix PR base SHA at creation: `979a305d848f8ec68ec3a460c36fec943421009e`, different from failing SHA. Review intervening branch history and mergeability before any merge.
- Commit-associated PR workflow lookup and combined status lookup for patch SHA returned empty; **no current passing CI attestation**. No full suite executed here. Existing historical failures are not evidence of a current-main failure.
- Remaining gate: independently run the patch branch's complete test matrix, verify required checks and skips, compare with current main, and document results. NO-GO until complete.

## PR #51 CI and branch reconciliation — 2026-11-09
- Historical branch `research/strategy-evidence-gates-v1` is **24 commits ahead** of the failing `1afceec5...` revision. Compare confirms it already changed `tests/unit/test_breakout_risk_replay.py` to numeric `Decimal` equality. The standalone fix is therefore redundant against the current target branch; do not merge solely to repeat this change.
- PR #51 head: `b877d92c3faabaaf9fb24888195c9dc9f8eddeff`. Its base at creation: `979a305d848f8ec68ec3a460c36fec943421009e`. Comparison: diverged, head 1 commit ahead and 24 behind the base.
- GitHub PR-triggered research workflow: https://github.com/alphatecau/alpha-labs/actions/runs/42552003295, job 128949423885 **success**. Job log checkout SHA: `d05ab27055f209e304f6af4b486aeca7901afab9` (PR integration SHA), **186 tests** reported; synthetic research fixture step succeeded.
- GitHub PR-triggered website workflow: https://github.com/alphatecau/alpha-labs/actions/runs/42552003259, job 128949423990 **success**. Same checkout SHA `d05ab27055f209e304f6af4b486aeca7901afab9`; **36 passed, 0 failed**.
- These are verified standard PR workflow results, **not** a full security/cryptography/historical-data matrix, nor proof of green current `main`.
- Historical breakout diagnostics workflow `.github/workflows/historical-breakout-research.yml` on target branch triggers only on push to `research/strategy-evidence-gates-v1` when that workflow file changes, or manual dispatch. It fetches external archives; it is not a routine PR check. No claim that this workflow was executed for PR #51.
- Node 20 deprecation warnings persist on standard CI jobs; non-fatal but should be scheduled for maintenance.
- Decision: historical assertion failure **resolved in target branch**; standard PR integration checks **PASS**; full Day 1 acceptance gate **PARTIAL / NOT CERTIFIED** until required coverage on pinned current-main or integration candidate is established. No merge, deployment, credential or trading changes.

## Day 1 main integration verification — 2026-11-09
- PR #50 current head `e64a9355d63cc5373747e4c975a9c35f56583d39`, base `main` at `2cb66a8ddfc2d2b64246ab9441d0a26a364f7360`, integration SHA `55efaa1bb9c381813fca48c0b0fc15547f133fd6` (verified PR metadata and job logs).
- Offline research CI: https://github.com/alphatecau/alpha-labs/actions/runs/42552141083, job `128949857862`: **success**, 212 tests, **3 skipped**; synthetic fixture passed.
- Website CI: https://github.com/alphatecau/alpha-labs/actions/runs/42552141054, job `128949857677`: **success**, 36 passed, 0 failed, 0 skipped.
- Three skipped security tests: `test_phase1_signed_archive.SignedArchiveTests.test_signed_bytes_and_tampering`, `test_phase2_archive_provenance.ArchivePhase2Tests.test_stream_limits_and_provenance_fail_closed`, `test_phase2_evidence_gate.EvidenceGateTests.test_valid_synthetic_archive_remains_unpromotable`. Runner lacks `cryptography`.
- Existing dedicated `.github/workflows/signed-archive-verification.yml` installs `cryptography>=44,<47`, runs the archive, evidence-gate and combined-promotion tests with explicit no-skips assertions, but path-filters its PR trigger to relevant code/workflow changes. PR #50 changes only audit documentation, so its successful generic CI **does not prove dedicated cryptography CI**.
- Existing `.github/workflows/paper-simulator-safety.yml` also uses path-filtered PR triggers, so PR #50 is not proof of that separate safety workflow.
- Current-main base SHA is independently confirmed by PR metadata, but no complete, no-skips security test matrix has been observed on the exact PR #50 integration SHA.
- **Decision:** standard CI PASS; full mandatory security verification **BLOCKED/UNVERIFIED**. Do not merge, deploy, change credentials or enable trading. The remaining action is to run dedicated security CI on the exact candidate or an equivalent pinned tree and inspect job logs; then certify only the tests actually run.

## Dedicated security CI candidate — 2026-11-09
- Created separate branch `audit/day1-dedicated-security-ci-20261109` from main SHA `2cb66a8ddfc2d2b64246ab9441d0a26a364f7360`.
- Draft PR #52: https://github.com/alphatecau/alpha-labs/pull/52, head `9c37ea55d69137953231ce467d4f8b5577611dea`, PR integration SHA `045938dabc46746e19095ec21dfe364dec2b18b2`.
- Added crypto-enabled full unit discovery with an explicit >=200 test threshold, zero-skips assertion and success requirement to the dedicated signed archive workflow; preserved existing targeted signed archive checks.
- Touched the paper simulator workflow only with an explanatory comment to trigger its existing PR-path-filtered adversarial pytest gate; no runtime trading code changes.
- Immediate PR workflow lookup returned **no runs** for either the head or integration SHA. This is an observation at lookup time, not proof that GitHub will never schedule checks. No new CI PASS claimed.
- Acceptance still **PENDING / NO-GO** until dedicated signed-archive, paper-simulator, generic research and website checks are observed with matching candidate SHA and passing logs.
