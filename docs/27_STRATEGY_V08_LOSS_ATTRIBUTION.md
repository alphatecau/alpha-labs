# Strategy v0.8 loss attribution

The rejected v0.8 strategy and its evidence remain in [draft PR #9](https://github.com/alphatecau/alpha-labs/pull/9), head `6f7b893ee4c319573bc23cc633f2fae6e90f7381`. The current audit rebuilt the inputs from the archived source and curated files. All three reports matched byte for byte. The separate indicator and float ledger reproduced 72,432 targets and 291 ledgers. The original GitHub [research](https://github.com/alphatecau/alpha-labs/actions/runs/42215273093) and [site](https://github.com/alphatecau/alpha-labs/actions/runs/42215273176) workflows succeeded at that head.

## Final historical test

The unsealed test covers 4,781 hours starting 15 June 2025 at 19:00 UTC. Each market starts at 10,000 USDT. Gross holds the modelled fills and quantities fixed and values them at the underlying hourly opens. Fees and the adverse price concession are separate model components. The latter combines spread and slippage, which hourly OHLCV cannot identify separately. No position was open at the end of this partition.

| Market | Gross USDT | Fees USDT | Price concession USDT | Overhead USDT | Net USDT | Net return | Positive forward folds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BTC | −54.16 | 63.31 | 63.31 | 65.49 | −246.27 | −2.463% | 1/14 |
| ETH | +101.76 | 68.52 | 68.52 | 65.49 | −100.78 | −1.008% | 4/14 |
| SOL | −176.05 | 69.61 | 69.61 | 65.49 | −380.76 | −3.808% | 4/14 |

| Market | Rerun with zero friction | Fees only | Price concession only | Base, zero overhead | Mean open notional / initial equity | Exposure-matched passive | Risk-matched passive |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BTC | −0.603% | −1.235% | −1.235% | −1.808% | 1.45% | −0.247% | −0.443% |
| ETH | +1.118% | +0.345% | +0.346% | −0.353% | 2.10% | +0.240% | +0.388% |
| SOL | −1.952% | −2.582% | −2.582% | −3.153% | 1.90% | −0.313% | −0.502% |

Cost ablations rerun sizing, risk and equity, with no scenario overhead. The matched buy-and-hold diagnostics use base friction and initial weights scaled retrospectively to the candidate's mean hourly notional or hourly P&L standard deviation, both normalised by starting capital. Neither was a live-calibrated benchmark. All three candidates trailed both matched exposures even with candidate overhead set to zero.

## Timing, turnover and regime

| Market | Trades | Win rate | Payoff | Profit factor | Net expectancy, USDT | Mean / median holding | Mean favourable / adverse excursion | Turnover / capital |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BTC | 56 | 16.1% | 2.05 | 0.393 | −3.23 | 21.4 / 5.5 h | +1.22% / −0.87% | 6.33× |
| ETH | 60 | 20.0% | 3.68 | 0.919 | −0.59 | 27.6 / 5.0 h | +3.00% / −1.48% | 6.85× |
| SOL | 62 | 22.6% | 1.46 | 0.425 | −5.08 | 25.2 / 7.5 h | +2.81% / −1.76% | 6.96× |

- The strategy entered only during its upward regime. Mean entry 72-hour momentum was 1.77%, 3.00% and 3.15% for BTC, ETH and SOL. Mean entry hourly volatility was 0.35%, 0.59% and 0.73%. Trade P&L at range-classified exit signals totalled −95.28, −96.52 and −155.72 USDT. These are entry-to-exit results, not P&L accrued exclusively during the exit regime.
- Of 169 signal exits, 146 occurred when 72-hour momentum fell below the entry threshold while the trend classifier still read upward. The next entry followed within 24 hours on 32/56 BTC, 35/57 ETH and 34/56 SOL signal exits. ETH signal exits still earned 44.61 USDT net before overhead. BTC and SOL signal exits lost 180.78 and 156.95 USDT. Separate close-triggered stops lost 79.89 USDT on ETH and 158.31 USDT on SOL. The reported mean hourly open versus previous close differences were under 0.1 bp in absolute terms, which says little about executable spreads, latency or tails.
- Gross fixed-fill P&L changed from +525/+230/+1,114 USDT in development to −147/−80/+143 in validation and −54/+102/−176 in the test. The model planned no more than 0.25% stop risk per entry. No base-case final-window daily or portfolio suspension fired. A small allocation dampened both gains and losses. Increasing size would not change the sign of the fixed-fill edge and could raise costs and drawdowns.

BTC and SOL lacked a gross edge in the final window. ETH's positive gross P&L was smaller than its combined modelled execution friction. Overhead compounded the losses in every market. The same momentum condition controlled entry and most signal exits, producing short median holding periods and frequent re-entry. A wider separation between entry and exit thresholds could reduce churn. Whether it improves net expectancy requires a separately registered comparison. Post-exit returns and within-bar excursions describe past paths and cannot establish that a different exit could have captured them.

The [machine-readable summary](evidence/strategy-v0.9/v08-loss-attribution.json) covers all partitions, exit cohorts, cost ablations and matched benchmarks. To export each underlying trade and its exact attribution, run `PYTHONPATH=packages/alpha_lab/src python scripts/attribute_strategy_v08.py --data-root /path/to/verified-data --output /tmp/v08-attribution.json --include-trade-ledgers`. Each window's ledger is fingerprinted in the summary. All analysis is retrospective.
