# Research Method and Technical Contracts — v0.2

## Project status

**Exploratory, browser-only simulation.** No historical market data has been verified, no independent backtest audit has been completed, and no live transactions are supported. The synthetic fixture intentionally serves only as reproducible interface demonstration.

## 1. Input contract

Each record supplies: `timestamp` (timezone-aware ISO 8601), `open`, `high`, `low`, `close`, optional `volume`. Values must be non-negative for volume and strictly positive for OHLC. `high >= max(open, close, low)` and `low <= min(open, close, high)`. Timestamps strictly increase. At least 30 records and no more than 20,000 records; text input ≤6 MB.

This parser cannot prove that the data came from a real exchange, identify missing market history, or prove complete coverage. It notes unusually large timestamp gaps using twice the median interval. It does not resample non-uniform data. All monetary results are in the **input price's quote currency**; the selected label has no conversion capability.

## 2. Signal timing / no-look-ahead contract

Bar `i` begins with a decision formed from bars `0 .. i−1` only.

- EMA rule: own the asset when `EMA_fast(i−1) > EMA_slow(i−1)` and the slow warm-up has completed.
- SMA rule: own the asset when `close(i−1) > SMA_slow(i−1)` and the slow warm-up has completed.
- No leverage and no short exposure.

Changing the close of bar `i` must not affect any trade at its *open* or earlier. Regression tests cover this property.

## 3. Simulated execution

For a model buy at opening price `p`: `fill_price = p × (1 + slippage_bps / 10000)`; buy fee = `fill_price × quantity × fee_bps / 10000`. The target notional is a user-selected fraction of available cash; both quantity and fees must fit cash.

For a model sell: `fill_price = p × (1 − slippage_bps / 10000)`; sell fee = `fill_price × quantity × fee_bps / 10000`. Positions are either held in full or sold in full when the signal turns flat.

The model's final open quantity is **not sold**. It is valued using an estimated liquidation value: `quantity × final close × (1 − slip) × (1 − fee)`. This estimate is not an observed executable quote. Strategy equity and benchmark equity both use this same conservative mark convention. Fees actually charged by the model are listed separately from an *estimated* future exit cost.

## 4. Passive benchmark

The baseline invests the same exposure percentage at the first strategy-eligible open, then holds. The fee and slippage model is the same on entry and on estimated closing valuation. The benchmark is not a risk-matched, dynamically rebalanced or tax-aware comparator.

## 5. Reported metrics

- Simulated net P&L = final model portfolio value − starting quote-currency capital.
- Net return = net P&L / starting capital.
- Max drawdown = peak-to-trough percentage change in estimated portfolio equity across the series.
- Closed-trade win rate = positive closed trade P&L count / total closed trade count. `N/A` for zero closed trades.
- Modelled fees and slippage costs are reported separately.
- Cost stress reruns the *same signal logic* at fees/slippage 1.0×, 1.5× and 2.0×.

This does not include mark-to-market uncertainty, taxes, variable routing and priority fees, opportunity costs, funding, reconciliation against brokerage statements, or live execution.

## 6. Required steps before any credible performance claim

1. Obtain and reconcile point-in-time market data with independent reference sources.
2. Formalise venue, quote currency, liquidity, conversion and corporate/action-like event handling.
3. Pre-register economic hypotheses and freeze model selection rules.
4. Introduce robust historical walk-forward testing, sealed holdouts, dependence-aware uncertainty and multiple-testing correction.
5. Replace fixed-slippage assumptions with actual executable-quote and fill feasibility modelling.
6. Collect independent forward data against frozen code and configuration hashes.
7. Independently audit portfolio accounting, risk restrictions and software deployment.
8. Conduct a separately approved and tightly capped real-execution pilot only when warranted.

**A positive result in this website is not sufficient to authorise real-money trading.**
