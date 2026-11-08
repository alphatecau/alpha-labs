# Phase 2 crypto-enabled CI verification and remaining release gates

Verified 2026-11-09 (Australia/Brisbane). Draft PR #35, head `24ad4e1d109bb9a35bba4803482ba18ea392e04f`.

## Independently inspectable GitHub evidence

- Full crypto-enabled research workflow run: https://github.com/alphatecau/alpha-labs/actions/runs/42532883655 — **success**.
- Job `full-crypto-research` ID: `128890787273` — **success**.
- Python `unittest` log: **234 tests executed; 0 skipped; all successful**.
- Previously skipped tests were explicitly logged as `ok`:
  - `test_phase1_signed_archive.SignedArchiveTests.test_signed_bytes_and_tampering`
  - `test_phase2_archive_provenance.ArchivePhase2Tests.test_stream_limits_and_provenance_fail_closed`
  - `test_phase2_evidence_gate.EvidenceGateTests.test_valid_synthetic_archive_remains_unpromotable`
- Generic offline research workflow run: https://github.com/alphatecau/alpha-labs/actions/runs/42532883586 — **success**.
- Existing Sites tests workflow run: https://github.com/alphatecau/alpha-labs/actions/runs/42532883612 — **success**.

## Scope of proof

These logs establish the tests ran successfully against a synthetic, isolated research codebase with the Ed25519 verification dependency installed. They **do not** prove independent historical capture, provider authenticity, source completeness, real-world fill quality, strategy profitability, or all deployed API entry points.

## Open controls

| Control | Evidence needed | Decision |
| --- | --- | --- |
| External archive trust root | Independent provider key fingerprint and out-of-band verification record, key rotation/revocation evidence | BLOCKED |
| Historical capture timestamp | Authenticated third-party receipt bound to immutable archive SHA-256 and capture time | BLOCKED |
| Runtime authorisation surface | Enumerated deployment routes, JS handlers, console entrypoints, role/access matrix and negative tests | UNVERIFIED |
| Real execution costs | Historical bid/ask/depth, fee schedules, market impact and slippage assumptions verified against source records | UNVERIFIED |
| Portfolio accounting | Independent trade-level reconciliation against sourced fills, holdings, cash and liquidation marks | UNVERIFIED |
| Sealed holdout and benchmark | Pre-registered out-of-sample evaluation with untouched periods and risk-matched benchmarks | UNVERIFIED |

## Release decision

**CI PASS / PRODUCTION NO-GO**. Keep PRs #28–#35 as drafts. Do not merge, deploy, change credentials, connect brokers, enable live trading or mark strategies profitable.
