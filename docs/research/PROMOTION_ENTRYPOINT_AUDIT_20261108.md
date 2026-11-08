# Promotion entry-point audit — scope and unresolved integration

Audited on the default branch after PR #22, while PR #23 remains open.

Known surfaces identified by repository code search:
- `research/assessment_cli.py::run_assessment` writes an offline assessment and already forces `promotion_authorised=False`. This PR explicitly records that archive provenance and capture attestation remain unverified.
- `research/evidence_gate.py::summarise_offline_research` returns `EVIDENCE_INSUFFICIENT_RESEARCH_ONLY`, `trading_enabled=False` and unverified price authenticity.
- `research/evidence_assessment.py::assess_evidence` computes research screening evidence, not a trading authorisation.
- `research/phase2_evidence_gate.py` is in unmerged PR #23; its callable evidence validation is not yet wired into assessment execution.

This PR introduces `decide_strategy_promotion` as a deny-only authority and tests forged positive flags. **It is not wired into every consumer or CLI**, and the search is not a complete call-graph audit. Do not interpret its existence as global enforcement. A subsequent integration PR must inventory all invocations and ensure every future promotion API/CLI routes through a single authority with a signed, independently verified evidence policy.

Existing historical rejected results are unchanged. No trading, brokerage, deployment or merge authorised.
