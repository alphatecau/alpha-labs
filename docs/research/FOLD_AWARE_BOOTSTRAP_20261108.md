# Fold-aware bootstrap — research diagnostic (8 November 2026)

## Motivation
The earlier `evaluate_oos` moving-block bootstrap treats concatenated fold observations as a single circular series. This permits artificial bootstrap blocks crossing fold boundaries and can misrepresent serial dependence. It remains as a **legacy diagnostic** for compatibility, not as the headline confidence bound.

## New method
`research/fold_bootstrap.py` draws circular moving blocks **independently within each fold** using a deterministic seed (42), 8-period blocks, 1,000 draws and a 95% one-sided lower quantile by default. Each fold retains its original number of observations; the aggregate estimate is an observation-weighted mean. Blocks never cross fold boundaries.

`research/evidence_assessment.py` now reports:
- `fold_aware_bootstrap_lower_bound` and `fold_aware_bootstrap_status=DIAGNOSTIC_ONLY`;
- `fold_aware_bootstrap_boundary_crossings=0`;
- `legacy_pooled_bootstrap_lower_bound_diagnostic_only` for transparent comparison;
- `lower_confidence_bound` from the fold-aware estimator, or null if it cannot run.

The fold-aware estimator fails closed when a fold is shorter than its block size. It does **not** infer statistical independence between folds, account for overlapping strategy development, correct multiple testing, prove executable prices or validate profitability. A positive lower bound is not a promotion signal. Overall assessment remains `INSUFFICIENT_EVIDENCE`, `trading_enabled=false`.

## Further research requirements
1. Compare block lengths and stationary/bootstrap variants under observed autocorrelation.
2. Review selection bias, multiple comparisons and independently sealed untouched holdouts.
3. Validate on authentic historical datasets with independent price checks.
4. Test realistic variable spread, impact, latency and exchange-specific fees.
5. Preserve draft PR and disabled trading until explicit authorisation.

## CI verification checkpoint
The regression test `test_fold_bootstrap_limitations_disclosed` was updated after the earlier failed run on commit `11c9be6`. Verify the complete current branch, not a rerun of that superseded commit. Passing earlier revisions does not certify the current head.
