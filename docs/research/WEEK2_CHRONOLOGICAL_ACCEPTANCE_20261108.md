# Alpha Labs Week 2 — Chronological validation execution register

**Branch:** `research/strategy-evidence-gates-v1` (draft PR #15).
**Safety:** live trading disabled; no merge, deployment, API keys, broker connections or orders.

## Committed implementation
- `scripts/week2_chronological_replay.py`: five disjoint chronological partitions with 48h embargo and independently reset simulated capital/positions. Causal breakout signals use earlier candles. Three assets × three fee/slippage levels, nine modelled combinations and 45 fold results.
- `research/causal_regimes.py`: linear-time prior-bar-only 168h trend / 48h volatility classification; classification is an **entry count**, not regime P&L.
- `research/selection_gate.py`: exact two-sided fold sign test and nine-comparison Bonferroni adjustment. Five folds have minimum two-sided sign-test p=0.0625, therefore cannot establish 5% familywise significance across nine comparisons. Fold independence is unproven; earlier adaptive selection is not adjusted.
- `.github/workflows/week2-chronological.yml`: unit tests, checksum-verified 2023-04..2025-12 archives, independent-reset model replays, and separately checksum-verified 2026-01..2026-10 data acquisition **without viewing later-period strategy returns**. JSON-only evidence artifact; raw market archives remain outside Git.
- Regression tests for embargoed windows, causal labels, and conservative inference.

## Important boundaries
The historical folds are new **model executions** but are not independently sealed walk-forward validations: the fixed strategy was selected after prior research on this history, and no training/refitting occurs within folds. The 2026-01..2026-10 later-period acquisition is a chronological later historical sample, not a prospectively independently sealed holdout. Do not call it untouched until a separate evidence custodian verifies non-use and pre-registration.

OHLC cannot establish actual executable stops; simulated fill and fee assumptions remain unverified. Global multi-market risk controls are not implemented. Five folds are too few for defensible significance given nine comparisons and previous adaptive strategy selection.

## CI acceptance
At commit `fb71e389381a2522e0aebb670fa92e39e8994c61`, commit-to-workflow lookup returned no PR-triggered runs. This connector does not expose push-triggered workflow discovery, so that result is **UNVERIFIED**, not failure or success.

Workflow: https://github.com/alphatecau/alpha-labs/actions/workflows/week2-chronological.yml

To complete verification, retrieve the workflow run ID, inspect jobs/logs, and inspect `alpha-labs-week2-chronological-evidence` JSON. Verify all 45 folds, all 9 independent accounting reconciliations per fold (45), all 3 later-period dataset checksums, no lookahead, no portfolio promotion, and no live execution.

**Current decision: NO-GO** for live trading, strategy promotion, merge or deployment.
