# Alpha Labs Week 3 — Pre-registered strategy discovery protocol
**Date:** 2026-11-08. **Branch:** `research/week3-preregistered-strategy-discovery`.
**Mode:** Research only; no live trading, deployment, merge, broker orders or credentials.

## Evidence baseline
Week 2 final GitHub run: https://github.com/alphatecau/alpha-labs/actions/runs/42472199571
Evidence artifact: 13613059109, SHA-256 `7107727020eda2dbd4af4bb20b417d079d4f36370321e0d943c93f19a13ee3b7`.
Breakout modelled net return (%) Jan–Oct 2026, BTC: -0.41/-1.16/-2.23; ETH: +0.42/-0.44/-1.66; SOL: +0.32/-0.17/-0.92 for 1x/2x/4x costs. This strategy is **rejected for promotion**. These outcomes are not a new holdout for Week 3 and must not be used to tune the new hypotheses.

## Data and evaluation
Development-only: checksum-verified Binance Vision 1h BTCUSDT/ETHUSDT/SOLUSDT 2023-04..2025-12. The 2026-01..2026-10 dataset has already been inspected and is excluded from all Week 3 hypothesis selection, tuning and validation. A genuinely prospective independent holdout must be collected after protocol freeze. Five contiguous chronological development folds with 48h embargo, 840h warmup, no future-bar features. Explicitly mark any folds on previously examined history as **retrospective diagnostic**, not independently out-of-sample.

Modelled starting portfolio equity 10,000 USDT. No leverage or shorting. Execute at next hourly open based on previous close. Fee and adverse slippage per side 10/10, 20/20, 40/40 bps. Cash holdings earn zero. Report modelled equity, net returns, max drawdown, turnover, closed trades, gross and net P&L, per-market allocation, and risk-matched passive/cash comparator. Reject missing candles, timestamps, negative equity, nonfinite values and unexplained reconciliation differences.

## Locked hypotheses (do not alter after inspecting outcomes)
**H1 Regime trend:** Long only when lagged close > lagged 168h simple moving average, lagged 48h return > 0.02, and lagged 48h realised volatility < 0.04. Exit when either trend condition fails. No lookahead.

**H2 Volatility-adjusted mean reversion:** Long only when lagged close is at least 1.5 standard deviations below lagged 48h mean, lagged 48h realised volatility < 0.035, and 168h trend absolute return < 0.05. Exit at mean or after 24 hours. No lookahead.

**H3 Cross-asset momentum rotation:** Every 24h rank BTC/ETH/SOL by prior 168h return; hold the single strongest positive-return asset, otherwise cash. All three verified histories must share an exact UTC hourly grid. No future prices.

## Portfolio authority
At most 20% of equity invested in H1/H2 single-asset diagnostics; H3 max 20% portfolio exposure in one selected asset, otherwise cash. 0.25% equity planned stop-risk budget per position, 1% aggregate stop-risk, 2% daily loss suspension, 5% peak-to-trough drawdown halt. 3x lagged 14h ATR stop, next-open gap exits conservatively modelled; no same-hour re-entry. Portfolio-level independent accounting ledger required. The initial research runner must fail closed if any control is not implemented; no claims of independent risk authorisation until verified.

## Selection and promotion
Three hypotheses × three cost tiers × three markets for single-market strategies plus 3 cost tiers for rotation: **21 registered comparisons**. Report all, including failures. Bonferroni familywise alpha 0.05 over 21 comparisons as a conservative *minimum* correction; also report prior adaptive selection, temporal dependence and repeated historical research as unresolved. With five folds, even 5/5 positive has exact two-sided sign p=0.0625 before correction: statistical promotion is impossible on five folds alone. No claims of alpha, profit, or production readiness. Promotion requires a prospectively sealed independent holdout, valid selection-aware inference, independently verified execution economics, and full portfolio risk authority.

**Acceptance:** Code and tests may pass; trading strategy decision remains INCONCLUSIVE or FAIL until independent evidence exists. No automatic strategy promotion.
