# Strategy Research v0.9 follow-up protocol

This is a bounded retrospective study on the verified April 2023 to December 2025 Binance Vision spot history. The six original trials and their rejection criteria are frozen in [the v0.9 registry](../configs/strategy-v0.9.json). The follow-up adds cost sensitivity and two development and validation diagnostics. Every added comparison is descriptive. The reserved 1 January 2027 to 1 January 2028 UTC prospective window stays outside the runner.

## Fixed cost grid

- Replay the six original signals across the three standalone markets and their shared-cash portfolio. Use the previously examined final partition and the same 14 forward folds. Keep the original decision schedule, risk limits, overhead and trial roles.
- Vary adverse concession at 0, 10, 20 and 30 bps per side with a fixed 10 bps fee per side. This gives 20, 40, 60 and 80 bps for a same-price round trip. Concession represents spread and slippage together. The frozen doubled-friction scenario instead uses 20 bps each for fee and concession per side. Keep both definitions explicit. The 40 bps case remains the primary comparison. A 20 bps scenario assumes zero price concession.
- Size positions separately for each cost case. Use 120 USDT per simulated 10,000 USDT account per year as a scenario expense, prorated by the scored hours. Report fixed-fill gross, modelled fees and concession, net, turnover, drawdown, close-mark drawdown duration, exposure and closed trades. Use the same timing for risk exits and the existing next-hour open for signal decisions.
- Retain the registered bootstrap family and original screen. The supplementary grid supplies no new selection authority, confidence claim or promotion decision.

## Exploratory matrix

| Test | Hypothesis | Comparator |
| --- | --- | --- |
| Four-hour trend with separate entry and exit thresholds | Keeping a position through small momentum reversals can reduce churn | Rejected v0.8 and matched passive |
| Four-hour relative-strength rotation | Concentrating in the strongest eligible asset may improve after-cost returns | Same trend rule without ranking and matched passive |
| Downtrend signal diagnostic | A bearish regime and negative momentum may precede negative next-four-hour returns | All available scheduled opens in the same market and partition |

Use the existing hourly v0.8 classifier and 72-hour price momentum at complete UTC four-hour boundaries. A current 72-hour volatility at least 1.5 times the previous non-overlapping 72-hour volatility, when the earlier volatility is positive, also sets the high-volatility state. Use the most recent 30 fully completed UTC daily closes, including the last one. Enter long in the uptrend state with momentum at least +1% and a daily close above its 30-day average. Exit on the downtrend state or non-positive momentum. Use the existing 4% stop distance and a four-hour cooldown after exit. The rotation variant keeps only the eligible leader by 72-hour momentum and exits when its leader changes or no long qualifies. Ties use the frozen BTC, ETH, SOL order. With no qualifying entry, the new position remains FLAT.

Count research SHORT observations only in the downtrend state with momentum at most −1% and a completed daily close below its average. Measure the underlying price return from the next hourly open to the open four hours later, wholly inside each scored partition. Report the sample count and fraction negative. This diagnostic has no positions, borrowing, funding, execution or net P&L. Use daily close-to-close correlations and maximum simultaneous positions within each partition to describe common exposure and concentration.

Score only the original development and validation partitions and full registered forward folds ending by the validation boundary. Reset positions and cash after the existing 48-hour embargo. Use preceding bars for indicators only. Compare against FLAT, passive, frozen EMA, shared v0.8, exposure-matched passive and risk-matched passive at 40 bps. `FAIL` if net is non-positive in development or validation at 40 bps, non-positive in validation at 60 bps, fails either available matched passive in validation, or reaches 5% drawdown in either validation scenario. Record whether 40 closed validation trades and both comparisons were available. Otherwise use `INCONCLUSIVE` because the data are previously examined. The runner has no promotion path.

## Verification and data provenance

The runner verifies source archives and pinned CSV hashes. It checks the exploratory signals against truncated inputs, replays fills, equity and risk state in the separate float implementation and records the source study and protocol hashes. Broker rejects, partial fills, executable liquidity, publication latency, short costs and account terms require separate evidence. Prices and vendor order books remain with the authorised research inputs. [Binance Vision data specification](https://github.com/binance/binance-public-data) · [Dataset terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md) · [Public fee schedule](https://www.binance.com/en-AU/fee/trading)

```sh
export PYTHONPATH=packages/alpha_lab/src
python scripts/strategy_v09_followup.py --data-root /path/to/verified-data --output /tmp/v09-followup.json
```
