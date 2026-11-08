# Phase 2 enforcement verification — 2026-11-09

Baseline: main `e43b2e199fdaae0a1cf7cc78e660f86a0642f675`. Research-only; no trading, deployment or credential changes.

## Entry points inspected
| Entry point | Authority boundary | Finding |
| --- | --- | --- |
| `research/assessment_cli.py` | `decide_strategy_promotion` | Explicit denial; archive gate not integrated |
| `research/evidence_gate.py` | `decide_strategy_promotion` | Deny-only |
| `research/strategy_evidence_bridge.py` | `decide_strategy_promotion` | Missing-provenance path previously omitted explicit promotion/live denial flags; fixed on this branch |
| `research/phase2_evidence_gate.py` | Signed bytes + chronology | Checks internal consistency, explicitly disclaims independent provider trust |
| `tools/local_research_server.py` | Read-only GET | POST 405; explicit false approval fields |
| `apps/sites/research-bridge.js` | Research-only UI | Rejects missing/positive approval fields |

This inventory is based on known entry points and repository code search, **not** a proven exhaustive call graph.

## Changes
- Add explicit false promotion and live-trading fields to the strategy bridge's missing-provenance return path.
- Add adversarial regression tests for forged approval flags, absent evidence, malformed archive inputs, and research-only boundary rejection.
- No permissive path, credentials, deployment configuration or broker integration added.

## Independent archive trust — BLOCKED
`phase2_evidence_gate` checks signatures and archive chronology but does not independently authenticate provider identity or timestamps. No independently controlled trust root or attestation has been supplied or verified. Do **not** treat signed-byte consistency or caller-supplied booleans as independent provenance. Integration with assessment CLI must remain deny-only until trust roots and archival capture evidence are independently established.

## Acceptance and follow-up
1. Run full CI and inspect actual job conclusions for this branch.
2. Execute unit tests including `test_phase2_fail_closed_regressions.py`.
3. Extend exhaustive call-graph and runtime route discovery across all executable entry points.
4. Require trusted archive verification as an assessment prerequisite; add negative tests for mismatched provider, timestamp, digest, and signer.
5. Independently verify holdout, cost and portfolio NAV accounting before considering strategy promotion.

**Decision: NO-GO.** No merge, production deployment, broker execution or live trading authorised.
