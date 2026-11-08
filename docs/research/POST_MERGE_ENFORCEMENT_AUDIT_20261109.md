# Alpha Labs post-merge enforcement audit — 2026-11-09

Baseline: PR #26 merged into main at `e43b2e199fdaae0a1cf7cc78e660f86a0642f675`.
Scope: connected GitHub PR metadata and complete seven-file PR patch. This is a static change review, **not** a complete repository audit or execution of tests.

## Verified in the merged patch
- `strategy_evidence_bridge.screen_research_report` routes numerical screening results to `decide_strategy_promotion`, with explicit false promotion and live-trading fields.
- Missing chronological observations return insufficient evidence and explicit denials.
- `local_research_server.load_snapshot` emits explicit false promotion and live-trading fields.
- Two Sites research consumers reject records lacking explicit false authorisation fields.
- New adversarial unit tests assert denial for forged positive flags, missing observations and caller-provided attestations.
- Local research server tests check GET denial fields and POST 405.
- GitHub PR page reports four successful checks, but individual job logs and execution results have not been independently inspected in this audit.

## Findings / residual risks
1. **HIGH — Incomplete entry-point coverage.** Prior audit explicitly disclaims an exhaustive import/call graph. Other CLI, API, batch, export and UI consumers may exist. Status: UNVERIFIED.
2. **HIGH — Unauthenticated research provenance.** Caller-provided point-in-time booleans do not prove independently authenticated provider identity or immutable historical capture. Status: NOT DEMONSTRATED.
3. **HIGH — Archive gate not mandatory.** Prior inventory says `phase2_evidence_gate.py` is not automatically called by assessment CLI. Status: OPEN INTEGRATION GAP.
4. **HIGH — Sealed holdout and independent reproducibility.** Independent sealed holdout, realistic execution costs and portfolio NAV accounting not demonstrated by PR #26. Status: UNVERIFIED.
5. **MEDIUM — Static source contract tests.** Tests asserting source strings do not establish browser/runtime behaviour or cover all external consumers. Status: PARTIAL COVERAGE.
6. **MEDIUM — Deny-only authority receives original report.** Bridge calls `decide_strategy_promotion(assessment=report)` rather than passing the computed numerical result. Current deny-only behaviour prevents authorisation; any future change to authority semantics requires separate trusted evidence inputs and tests. Status: DESIGN RISK.

## Required follow-up tests (not yet executed)
- Enumerate all executable entry points, imports, routes and approval-like fields; assert every consumer fails closed on absent, malformed and forged permissions.
- Mutation-test the authority and downstream adapters against truthy strings, missing fields, nested flags and positive forged attestations.
- Prove archive gate is required by the assessment path, with independently verified signatures, trusted public keys and timestamp attestations.
- Validate causal source provenance, sealed holdout isolation, risk-matched benchmarks, cost decomposition, portfolio NAV accounting and deterministic replay.
- Inspect post-merge CI logs and run full tests on the exact main SHA; document environment, command, results and artifact hashes.
- Obtain independent reviewer approval before any change to promotion policy.

## Decision
**NO-GO:** strategy promotion, live trading, broker execution, production deployment and credentials remain disabled. No evidence of strategy profitability or production readiness is established by this review.

This document records an audit finding only. It is not permission to enable trading, merge a branch or deploy.
