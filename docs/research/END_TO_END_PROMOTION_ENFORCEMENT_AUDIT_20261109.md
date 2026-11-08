# End-to-end promotion enforcement audit — 2026-11-09

Baseline: main after PR #25 (merge 4e24bb2e7e3eb33b8829dc64910646784d0c1afd).

## Code-search inventory (not a complete call graph)
- `research/assessment_cli.py`: calls deny-only `decide_strategy_promotion`; report includes explicit false approval and trading fields.
- `research/evidence_gate.py`: hypothesis-screen summary calls deny-only authority.
- `research/strategy_evidence_bridge.py`: **this branch now calls deny-only authority** after quantitative screening, and emits explicit false approval/trading fields on insufficient evidence.
- `research/evidence_assessment.py`: lower-level numerical evidence screening; returns `trading_enabled=False` but does not issue an approval.
- `research/phase2_evidence_gate.py`: validates signed archival bytes and chronology, explicitly returns promotion/trading ineligible, but is not automatically called by assessment CLI.
- `tools/local_research_server.py`: local read-only GET endpoints; POST returns 405; no order endpoint found in inspected code.
- `apps/sites/research-bridge.js`: read-only research display, requires `trading_enabled===false`.
- `research/promotion_authority.py`: deny-only; no automatic approval capability.

## Threats and limitations
- A caller-supplied boolean `point_in_time_provenance_verified=True` in the legacy strategy bridge is **not independent evidence**. The bridge can perform numerical screening, but cannot approve trading or promotion.
- No independently authenticated provider identity, immutable third-party historical capture receipt or sealed holdout has been demonstrated.
- The audit used repository code search and selected file inspection, not exhaustive runtime route discovery or a formal security review.
- The new tests exercise forged positive fields at the strategy bridge. They do not prove all external consumers respect those fields.
- The code has **no approved live trading route**; do not add brokerage execution, deployments, production credentials or approval flags.

## Required next gates
1. Complete repository-wide API/CLI/UI entry-point and import call-graph audit.
2. Require cryptographically verified external archive trust roots and timestamp attestations.
3. Integrate evidence checks into assessment inputs, with independent source authentication.
4. Independently sealed holdout, realistic execution costs, reproducible risk accounting and adversarial tests.
5. Independent review before any future strategy promotion or deployment authorisation.

**Decision: NO-GO for strategy promotion, live trading and deployment.**
