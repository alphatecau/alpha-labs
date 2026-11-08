# Alpha Labs — Independent strategy evidence screening v1

Scope: research-only statistical screening. No trading, broker connectivity, MiroFish, LLMs, deployment or production changes.

## Inputs and limits
`evaluate_oos` accepts a chronological immutable tuple of already-net per-period out-of-sample returns, total trade count, independent fold-level net returns, and an **additional per-period** cost stress. It does not infer trade count from returns or verify input provenance. Do not confuse per-period costs with round-trip transaction costs: compute realistic turnover-dependent fees, spread, slippage and impact upstream before calling this screen.

Default conservative rejection gates: at least 120 periods, 40 trades, 3 folds with a strict majority positive, positive circular moving-block bootstrap lower bound (1,000 resamples; 95% one-sided bound), and positive stressed average net period return. Drawdown is measured from the chronological supplied series. A successful screen is labelled `REVIEW_REQUIRED`, never profitable, validated or production-ready.

The bootstrap is descriptive, **not** a multiple-testing-corrected or independent significance proof. Block size must be justified using measured autocorrelation; highly overlapping or nonstationary observations invalidate naive confidence interpretations. Synthetic fixtures only test engineering behaviour.

## Required upstream evidence before any strategy promotion
1. Immutable UTC timestamped raw data, quote integrity, corporate actions where applicable, and point-in-time provenance.
2. Pre-registered strategy hypothesis and parameters; train/validation/test separation with purge and embargo based on maximum lookback and label horizon.
3. Walk-forward folds and untouched sealed holdout, with no hindsight selection of the best variant.
4. Correct accounting for spread, maker/taker fees, slippage, market impact, borrow/funding, API/compute costs and order constraints.
5. Multiple-comparison and data-snooping controls; compare with passive and simple baseline strategies.
6. Independent reproducibility, adverse regime tests, sensitivity, trade-level bootstrap and realistic executable-fill model.
7. Independent risk authority and separate paper-only approval. Live trading remains disabled.

Run: `PYTHONPATH=packages/alpha_lab/src python -m unittest discover -s tests/unit -p 'test_strategy_evidence.py' -v`.

This branch is deliberately separate from paused draft PR #14.
