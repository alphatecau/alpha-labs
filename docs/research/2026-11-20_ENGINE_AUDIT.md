# Research engineering audit — 20 November 2026

Scope: inspected repository modules `data/csv_import.py`, `research/metrics.py`, `research/strategies/momentum.py`, `backtest/costs.py`, `backtest/engine.py`. This is a source review, not an independent market-data or execution audit.

## Findings
- CSV loader enforces timezone-aware UTC, positive finite OHLC, volume >=0, chronological exact intervals, >=80 bars, SHA-256 raw bytes, and explicit quote unit. **Limitation:** arbitrary user-supplied provenance string is not source authentication; the loader does not prove publication time, venue identity, or complete/executable prices.
- Baseline computes EMA from completed closes; engine uses `signals[i-1]` at next candle open. **Limitation:** assumes fill at next open with fixed adverse slippage, without spread/depth/latency/partial fills.
- CostModel charges per-side percentage fee and adverse slippage and supports doubling both. It does not validate observed venue fees or model funding, taxes, FX, market impact, operating costs.
- Replay tracks Decimal cash and inventory, buy/sell fees, conservative liquidation NAV, and drawdown; it does not expose a complete per-bar independently reconciled cash/inventory journal. Reference-ledger fixture tests are not full engine-to-ledger replay parity.
- `research/metrics.py` performs 70/30 chronological train/holdout without embargo and labels its holdout descriptive/unsealed. The frozen multi-year evidence separately records 60/20/20 partitions with 48-hour embargo. These are **distinct methodologies** and must not be presented as equivalent.
- Original frozen multi-year audit is SHA-256 locked; original EMA test losses are not rewritten or retuned.
- R1 is fixed to EMA12>EMA48, close>SMA200, and 48-bar realised log-return volatility <= nearest-rank 75th percentile of prior 720 volatility observations. It uses only completed candles and next-open replay.
- New R1 comparator accepts user-provided development CSV only, refuses bars in reserved 2027 calendar year, and labels 70/30 outputs unsealed. Its split is NOT a sealed prospective or 48-hour-embargoed multi-year walk-forward evaluation.

## Acceptance blockers (fail closed)
1. GitHub Actions passing run, complete regression suite and executable environment evidence.
2. Reproduce and independently reconcile full engine order journals, NAV, fees and costs across real source-backed folds.
3. Venue-authenticated provenance and transaction-cost calibration; observed spread/depth and time-of-publication checks.
4. Predeclare a truly embargoed walk-forward protocol, register exact immutable input manifests, and use independently custodied future holdout.
5. Evaluate R1 with source-verified data and report fold-by-fold economic P&L, uncertainty and multiple-testing limits.

No new profitability claim, no live trading, wallet signing, leverage, execution, or deployment is authorised by this work.
