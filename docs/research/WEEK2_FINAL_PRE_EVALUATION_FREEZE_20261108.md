# Week 2 final validation — FROZEN protocol BEFORE 2026 evaluation

Frozen on 2026-11-08, before any Jan–Oct 2026 strategy replay by this workflow. This is a **retrospectively selected strategy**, not a prospective preregistration and not an independently sealed holdout.

## Locked input data
Source: Binance Vision verified spot monthly 1-hour candles, January through October 2026, 7,296 bars per market, verified in GitHub run 42471717885; artifact 13613439312. Do not include November 2026. **Exact curated CSV SHA-256:**

| Market | CSV SHA-256 | Manifest SHA-256 |
|---|---|---|
| BTCUSDT | `c11dd11b0d2c7fb0b962a43efdf64c23f68197043ef8c72e36c9ce82c880b3c0` | `af94bb66ee1df10fb80b7c84135ddc8404364fa004e3f4fb7ce1c5c235c5a4cc` |
| ETHUSDT | `e43a249dfef1604a696856365899d405ecbf52ff9efe9f1e97f11cdfadf1fd8b` | `fc52ad44de07668280cd651ca0fe0fb8f9875973dc2f9144f058be7017417b0e` |
| SOLUSDT | `10878933a0cb8737a7879d7827b9cda440e7a38a36a73d9a13747b2e37c49180` | `6807be2076e75cbf5deb854813c7dd50adafd83ca96691204364a49147a5548d` |

## Locked strategy and costs
Long/flat only; completed 4h breakout, 20-candle breakout lookback, 200-candle EMA, 10-candle EMA slope, 14-candle ATR, 30-candle maximum hold, 3× ATR trailing and stop, ATR/close between 0.005 and 0.06. Starting modelled cash 10,000 USDT per market/cost; planned position loss <=0.25% starting cash; maximum allocation 20%; 2% daily suspension; 5% drawdown halt. No portfolio-level authority. Fees and adverse slippage per side: (10,10), (20,20), (40,40) bps. No parameter tuning.

Git blob SHA locks: breakout signal `08f3e347e7b03fcd41a1e14a4c91c53ca207183a`; risk replay `4494ce502355bee304442cde3d5c80acd166b950`; nine-comparison inference gate `1717cdfa8b8ee5571dbed4e06b4c1a7ccd44bfc4`. The evaluator must assert these exact blob hashes using `git hash-object` before reading forward prices. If any source changes, abort.

## Locked evaluation
One research-only replay per market × cost combination on 2026-01..2026-10, with 840 hourly warmup bars. Report 9 return percentages, maximum drawdowns, closed trades, fees, source hashes, accounting reconciliation and PASS/FAIL/INCONCLUSIVE. The same 2026 prices may be downloaded repeatedly to verify integrity, but strategy evaluation must be run only once. The result file must not be overwritten. No optimisation or parameter adjustment after viewing outcomes.

## Locked statistical and promotion gates
Five historical independent-reset folds previously examined, with exact two-sided sign-test and Bonferroni across 9 asset/cost comparisons; minimum unadjusted p=0.0625 for five positive folds, therefore no statistically significant historical result. Previous adaptive candidate selection, overlapping market exposure and fold dependence are not corrected by this gate. The later-period one-shot replay provides **descriptive out-of-period evidence**, not an independent prospective experiment; do not compute or claim a valid selection-adjusted p-value from one period. 

- **PASS (engineering only):** all hashes match; all 9 evaluations complete; all 9 accounting checks PASS; output immutable and safety flags false.
- **FAIL (engineering):** any hash, replay, accounting or data-integrity failure.
- **INCONCLUSIVE (strategy):** regardless of positive returns until a separately preregistered prospective holdout, defensible selection-aware inference, risk authority and executable-price evidence exist.
- Live trading, deployment, merge, strategy promotion and broker orders: **PROHIBITED**.
