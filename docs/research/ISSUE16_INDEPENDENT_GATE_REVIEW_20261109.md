# Issue #16 — Independent integration gate review (2026-11-09)

**Decision: NO-GO / BLOCKED. This is a review record, not a code merge or correctness certification.**

## Pinned observations
- Main: `e43b2e199fdaae0a1cf7cc78e660f86a0642f675` (includes merged #26).
- Preserved Phase 1 research branch: `research/phase1-integrated-audit-20261108` at `30ce4530ca7c21c3c209e6dc4a57365d528f2b7c`.
- GitHub compare main...Phase 1: **111 ahead, 10 behind**, merge base `9d705bd1982396b19006b9abd3ec8b6a254f2972`. Prior issue's 111/1 count is stale.
- Existing Phase 1 integration PR #17: head `faa52e80dfdf07c016ecd40cfe3b797a13c7432c`, open, **not draft** according to API, 72 changed files; its own description says PR #15 is not reconciled and independent complete CI is missing.
- Phase 2 combined draft PR #34: head `4a1d3ae2bf181290eef32314ebea316f51f60bda`, 14 changed files, mergeable per GitHub metadata (not proof of safety).
- Phase 2 crypto-enabled CI draft PR #35: head `51b8863fed607db7e34037b43fa0f84926cbb304`, targets PR #34 integration branch; its description records three skipped provenance tests in generic CI and demands no skips.

## Acceptance decisions
| Gate | Status | Required evidence |
|---|---|---|
| Exact branch SHA inventory | PASS (metadata only) | Recheck before review |
| Phase 1 / PR #15 evidence reconciliation | BLOCKED | Single explicit fail-closed promotion policy, no contradictory bridges |
| Phase 1 reconciliation against current main | BLOCKED | New integration tree, conflict review, no history rewrites |
| Independent Decimal NAV/cash/partial fill/short oracle | UNVERIFIED | Independently executed fixtures and reproducible results |
| Point-in-time and prospective holdout integrity | UNVERIFIED | Provenance, lag, calendar, purge/embargo and sealed data checks |
| Costs and risk-matched benchmark verification | UNVERIFIED | Negative/adversarial cost and look-ahead fixtures |
| Complete combined-tree CI | UNVERIFIED | Exact SHA, workflow URLs, job logs, counts, skip counts and hashes |
| External archive trust and real-market evidence | BLOCKED | Independently sourced trust roots, signed manifests and datasets |
| Promotion, deployment and trading | DENIED | Separate explicit authorisation only after all gates pass |

## Safe execution order
1. Review PR #17 against **current** main and identify duplicate evidence-authority paths; preserve source branches.
2. Reconcile on a new, separate integration branch only, documenting conflict decisions. Never treat an automatically mergeable tree as verified.
3. Run independent accounting oracle, timestamp/data, costs, benchmarks and adversarial evidence tests.
4. Verify all workflow jobs, skipped tests and artifacts on exact integrated HEAD; rerun after any changes.
5. Obtain independent review and record PASS/FAIL/BLOCKED/UNVERIFIED for every gate before requesting merge authorisation.

No merge, deploy, secrets, broker connection, capital release, live trading or strategy promotion authorised. Prior rejected strategies remain rejected. Green CI is not evidence of profitability.
