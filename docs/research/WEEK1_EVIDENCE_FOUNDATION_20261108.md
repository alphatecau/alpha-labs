# Alpha Labs — Week 1 evidence-foundation acceptance record

**Date:** 2026-11-08
**Branch:** `research/strategy-evidence-gates-v1` (draft PR #15)
**Safety:** research only; no merges, deployments, broker calls, or live trading.

## Completed in this batch
- Reviewed existing offline CI workflow `.github/workflows/research-ci.yml`, breakout signals, next-open replay, CSV ingestion, Binance archive verification, and preregistered candidate protocol.
- Closed a provenance bypass in `research/breakout_evaluation.py`: non-synthetic data now require `verify_dataset` against a Binance Vision archive manifest and cached source archives. A descriptive string alone is not sufficient.
- Explicitly label synthetic fixture reports and disclose that independent price authentication and complete portfolio risk enforcement are not provided by the current replay.
- Added `scripts/breakout_archive_research.py` to preflight all three archive-verified markets and produce immutable 1×/2×/4× modelled fee/slippage cost-stress reports, with fail-closed outputs and no live execution.
- Added regression tests for missing manifests, unverified source labels, duplicate symbols, invalid evaluation windows and research-only disclosures.

## Execution (requires existing verified datasets)
```sh
export PYTHONPATH=packages/alpha_lab/src
python -m unittest discover -s tests/unit -p 'test_*.py' -v
python scripts/multi_year_research.py fetch --symbols BTCUSDT ETHUSDT SOLUSDT --from-month 2023-04 --through-month 2025-12
python scripts/multi_year_research.py verify --symbols BTCUSDT ETHUSDT SOLUSDT --from-month 2023-04 --through-month 2025-12
python scripts/breakout_archive_research.py --data-root datasets --output-root datasets/replay/breakout-20261108 \
  --from-month 2023-04 --through-month 2025-12 --start-index 840 --end-index 1000
```
The final example uses a **short diagnostic window**, not the complete preregistered walk-forward experiment. It must not be interpreted as independent validation. The runner does not automatically select valid walk-forward boundaries, account for cross-asset correlations or enforce the full risk policy.

## Explicit outstanding gates
1. **Latest commit CI:** must verify the GitHub Actions run on the actual current branch head. A successful older commit is insufficient.
2. **Real data:** no genuine BTC/ETH/SOL archive download or replay was executed through this connected development session. Archived raw/curated datasets are gitignored.
3. **Strategy execution correctness:** current next-open replay models a signal-based close on the next hourly open; it does **not** model intrabar stop triggers, gap fills at stop thresholds, independent per-position 0.25% stop risk, daily 2% HALT, portfolio 5% HALT or aggregate stop risk. Do not claim the preregistered stop-loss strategy is fully implemented.
4. **Accounting:** the existing independent reconciliation module must be applied to candidate reports; the breakout runner does not yet perform that reconciliation.
5. **Independent holdout:** 2023-04 to 2025-12 has been previously examined and is not sealed. No strategy is approved, profitable or production-ready.

**Week 1 decision:** Code-level provenance and runner safeguards implemented; full evidence-foundation gate remains **BLOCKED / UNVERIFIED** until CI, risk-model parity, real data and accounting are confirmed.
