# Alpha Labs — Preregistered candidate discovery protocol v0.1

**Date:** 2026-11-08. **Status:** RESEARCH HYPOTHESIS ONLY / NO PROFITABLE EDGE ESTABLISHED.
**Execution:** disabled; no broker or exchange credentials. Draft PR #15 remains unmerged.

## Decision and data boundary
Candidate: **long/flat 4-hour volatility breakout**, benchmarked against frozen EMA(12,48) and matched-allocation passive holding. This is not a short-selling experiment: Binance Vision spot OHLCV does not contain borrow rates, derivatives funding or executable short quotes.

Data: Binance Vision BTCUSDT, ETHUSDT, SOLUSDT monthly **spot 1-hour** klines, April 2023–December 2025, with published ZIP checksums and strict UTC hourly completeness checks. January 2025 onward spot timestamps are microseconds. Reuse the repository's existing `scripts/multi_year_research.py` fetch/verify path; do not bypass its source-integrity checks. Provider hashes establish archive consistency, not independent price authenticity.

**Important contamination boundary:** April 2023–December 2025 has already been examined during Alpha Labs development. It is development/research evidence, **not an untouched holdout**. Do not claim independent confirmation on that window. A subsequent, chronologically later preregistered holdout, obtained and sealed *before reviewing strategy outcomes*, is required for independent validation. No historical data already viewed by developers can be relabelled sealed.

## Frozen candidate specification (to implement before viewing new results)
- Construct 4-hour OHLCV from four complete, consecutive 1-hour candles, UTC-aligned. Fail closed on missing or duplicate hours. Decisions use only completed candles.
- LONG entry: close of most recent completed 4-hour bar strictly exceeds maximum high of the **previous 20** completed 4-hour bars; close above 200-bar EMA; EMA(200) slope over the prior 10 completed bars positive.
- Volatility filter: ATR(14) / close within 0.5%–6% on the signal bar. These are predeclared *assumptions*, not tuned values.
- Signal at 4-hour close; earliest modelled fill is the **next available 1-hour open**. Never fill on the signal candle.
- Long/flat only. No leverage, borrowing, shorts or discretionary overrides.
- Exit: stop at 3 × ATR(14) below highest completed 4-hour close since entry; also exit after 30 completed 4-hour bars, or on close below EMA(200). For gap-through-stop, model fill no better than next available hourly open; explicit adverse slippage and costs still apply.
- Allocation cap 20% equity; independent risk policy must enforce per-position planned stop loss <=0.25% equity, aggregate planned stop risk <=1%, daily loss HALT at 2%, drawdown HALT at 5%, gross notional <=1× equity. If risk checks cannot be enforced, **do not trade**.
- Fees and adverse slippage: initial diagnostic 10 bps each side for each component, plus stress at 2× and 4×. These assumptions are not executable prices or verified actual exchange fees. Model spread/impact separately when quote data become available.

## Statistical design
- Development: walk-forward chronological training/validation, embargo >=48 hours, strictly causal features and no look-ahead.
- Comparator: matched allocation passive spot holding, no-trade, existing EMA baseline.
- Account for **all tested candidates** in a strategy search register; do not choose the best-performing asset, block length or cost case post hoc.
- Fold-aware block bootstrap sensitivity at 4/8/16 observations is diagnostic only. Do not treat multiple folds as independent samples, or a positive confidence bound as sufficient evidence of alpha.
- Acceptance *for further independent holdout testing*, not live deployment: net return after stressed costs >0, positive passive-relative excess, >=40 closed trades across sufficiently independent folds, positive lower confidence bound under each preregistered block length, no severe concentration in one asset/fold, no risk-policy violations, independent NAV/order/fee reconciliation. Report exact denominators and uncertainty. Failure of any required gate => REJECT/INSUFFICIENT_EVIDENCE.
- A separately sealed forward holdout, broker-grade executable quote simulation, and paper trading with reconciled costs are still required for any production consideration.

## Execution sequence
1. `export PYTHONPATH=packages/alpha_lab/src`
2. `python scripts/multi_year_research.py fetch --symbols BTCUSDT ETHUSDT SOLUSDT --from-month 2023-04 --through-month 2025-12`
3. `python scripts/multi_year_research.py verify --symbols BTCUSDT ETHUSDT SOLUSDT --from-month 2023-04 --through-month 2025-12`
4. `python scripts/multi_year_research.py freeze --symbols BTCUSDT ETHUSDT SOLUSDT --from-month 2023-04 --through-month 2025-12`
5. `python scripts/multi_year_research.py evaluate --symbols BTCUSDT ETHUSDT SOLUSDT --from-month 2023-04 --through-month 2025-12`

**Warning:** The commands above run the existing EMA baseline, NOT the proposed breakout candidate. Do not mislabel baseline reports as breakout results. The breakout engine, risk integration and tests must be implemented and verified before any breakout performance claim.

## Current result
No fresh archive download or full replay completed in this execution. The environment cannot resolve public download hosts; GitHub-connected code inspection alone does not expose gitignored raw/curated datasets. **Profitability: UNVERIFIED. Trading: DISABLED.**
