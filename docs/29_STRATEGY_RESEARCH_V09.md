# Strategy Research v0.9

**6 November 2026 · FAIL for all registered variants · Research only**

The four-hour breakout had the best final historical portfolio return. It earned 1.724% after the modelled costs and overhead, including 0.903% at doubled friction. It failed the consistency screen with 5 of 14 positive forward folds, and its 27 closed trades fell short of the 40-trade portfolio minimum. The other two primary variants and all three sensitivity variants also failed. All 48 adjusted descriptive lower bounds were below zero.

Review the [v0.8 loss attribution](27_STRATEGY_V08_LOSS_ATTRIBUTION.md), [strategy research review](28_STRATEGY_RESEARCH_REVIEW.md) and [evidence index](evidence/strategy-v0.9/index.json).

## Registration and data

The registration commit was [`2d082f2500bf29a31b76e3598735e02464637881`](https://github.com/alphatecau/alpha-labs/commit/2d082f2500bf29a31b76e3598735e02464637881), before any v0.9 candidate runs. [The registry](../configs/strategy-v0.9.json) has SHA-256 `f93bbc00d9bedf7880bc2b51820a71820c18ee879e5d7d1263a7e6f71c6568c5`. It fixes three primary rules, one neighbouring configuration each, scoring and all costs. The neighbours measure parameter sensitivity and are ineligible for selection.

The v0.9 branch is based on v0.8 at `6f7b893ee4c319573bc23cc633f2fae6e90f7381`. Its draft review base is `research/strategy-v0.8`, so the new research can be reviewed separately from the failed strategy in [draft PR #9](https://github.com/alphatecau/alpha-labs/pull/9).

The runner verifies 99 source archives and the exact curated CSV and manifest hashes for 72,432 BTCUSDT, ETHUSDT and SOLUSDT observations. Every observation comes from the previously examined April 2023 to December 2025 history. Fixed partitions exclude 48 hours before validation and test. Forward folds each exclude their first 48 hours, allow older bars only for causal features and restart capital, positions and loss suspensions. The variants use fixed rules and have no trained labels. Scored periods and folds overlap, and the three markets are dependent.

## Final unsealed shared-capital results

15 June 2025 19:00 UTC to 1 January 2026 00:00 UTC, exclusive. All six runs start with one 10,000 USDT balance. Gross holds the fill quantities and reference prices fixed and removes fees and price concessions. Net includes the scenario charge of 120 USDT/year, which contributes 65.49 USDT to this window. The latency column delays discretionary signals by one additional hour at base friction. Stop and time-based risk decisions keep their registered timing.

| Variant | Gross | Net at base | Net at 2× | Net with delay | Max drawdown base / 2× | Closed trades | Positive folds | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Four-hour breakout | +3.051% | +1.724% | +0.903% | +2.300% | 1.956% / 1.878% | 27 | 5/14 | FAIL |
| Four-hour breakout neighbour | +2.580% | +1.296% | +0.548% | +1.503% | 2.227% / 2.130% | 25 | 5/14 | FAIL |
| Daily breakout | +0.369% | −0.369% | −0.451% | −0.275% | 1.538% / 1.498% | 7 | 3/14 | FAIL |
| Daily breakout neighbour | +0.424% | −0.302% | −0.378% | −0.206% | 1.353% / 1.319% | 6 | 3/14 | FAIL |
| Four-hour mean reversion | −2.613% | −5.147% | −5.456% | −5.222% | 5.002% / 5.092% | 58 | 4/14 | FAIL |
| Four-hour mean reversion neighbour | −2.842% | −5.142% | −5.256% | −3.835% | 5.107% / 5.016% | 51 | 4/14 | FAIL |

| Primary variant | BTC net base / 2× | ETH net base / 2× | SOL net base / 2× | Shared portfolio net base / 2× |
| --- | ---: | ---: | ---: | ---: |
| Four-hour breakout | −0.275% / −0.525% | +1.194% / +0.842% | −0.501% / −0.714% | +1.724% / +0.903% |
| Daily breakout | −0.833% / −0.857% | −0.204% / −0.247% | −0.640% / −0.656% | −0.369% / −0.451% |
| Four-hour mean reversion | −3.864% / −4.479% | −2.196% / −2.542% | −0.477% / −0.935% | −5.147% / −5.456% |

- The four-hour breakout spent 67.28 USDT on fees and adverse price concessions in the base portfolio run. Its 68-hour median closed hold and 3.36× turnover on a shared account contrast with median holds of 5–7.5 hours and turnover of 6.33–6.96× in the separate v0.8 accounts. The different sizing and capital structure prevent attributing the full difference to entry/exit timing. Portfolio profit factor was 1.86 and mean closed expectancy was 8.81 USDT before scenario overhead. Base return was +10.460% in development and −1.436% in validation over different window lengths. The stronger one-hour-delay result is a stress observation and carries no selection authority.
- The daily breakout reduced turnover to 0.41× and made 28.63 USDT after friction before overhead on the shared account. The small gross edge and seven closed trades were insufficient. The four-hour mean-reversion portfolio had negative gross P&L, with 45 of its 58 closed trades entering when the independent hourly v0.8 classifier showed a downtrend. The registered ten-day range filter can permit shorter downtrends. This distinction motivates a future hypothesis and does not justify changing this experiment.
- Base portfolio comparators were FLAT at 0.000%, frozen EMA(12,48) at −6.356%, equal-weight passive at −1.320%, and shared v0.8 at −4.462% after the same scenario overhead. The four-hour breakout beat exposure-matched passive by 1.950 percentage points and risk-matched passive by 2.084 points. Passive matching scales initial weights retrospectively to the same mean hourly notional or hourly P&L standard deviation. The single-market EMA and passive comparators reproduce the old account balance and fill count.

## Risk, costs and uncertainty

- Simultaneous entries share cash. Admission applies the friction-inclusive planned loss per position and the remaining aggregate allowance against current equity. Highest aggregate planned risk observed at entry in the reported candidate partitions was 0.753% of equity. Observed open/close portfolio drawdown exceeded 5% in mean-reversion runs despite suspensions. At an hourly opening gap, the stop reference can be missed. A within-hour touch is modelled at the stop less adverse concession and fee. The liquidation estimates, stop timing and thresholds do not guarantee realised loss or fill price.
- The 10 bps fee and 10 bps concession per side are model inputs. The 2× case doubles both and resizes the positions. The OHLCV records cannot resolve depth, quotes, fill fraction, slippage distribution, tick/lot constraints or delay at the stop. The observed fill share of hourly base volume is descriptive and cannot establish capacity. Account eligibility, independently authenticated venue prices, historical data release timing, executable costs and USDT/AUD conversion remain unverified. The [research review](28_STRATEGY_RESEARCH_REVIEW.md#execution-economics-and-evidence-limits) lists source and calibration requirements.
- The reported performance ratios use hourly marked net equity before the hypothetical operating expense. Expected shortfall averages losses in the worst 5% of hourly returns. The bootstraps use 199 complete UTC days and 14-day blocks with 16,384 draws. One-sided Bonferroni adjustment covers 48 paired variant, scope and comparator tests. For the leading portfolio, the lower bounds are −2.751 bps/day versus FLAT and −2.170 bps/day versus matched exposure. These are descriptive uncertainty estimates on previously examined data.

## Reproduction and next gate

With Python 3.12+ and the `raw/` and `curated/` trees from the verified historical bundle, run the following from the repository root. Each output directory must be new. The script uses the standard library and the existing archive verifier. It was run on Linux. A physical Termux run is unverified.

```sh
export PYTHONPATH=packages/alpha_lab/src
python scripts/strategy_v09.py --data-root /path/to/verified-data --output-dir /tmp/alpha-v09 --verify
python scripts/strategy_v09.py --data-root /path/to/verified-data --output-dir /tmp/alpha-v09-repeat --verify
diff -rq /tmp/alpha-v09 /tmp/alpha-v09-repeat
make verify
```

Both full runs produced identical evidence bytes. The separate float implementation reproduced 434,592 signal slots, 894 replays, 2,070,576 hourly equity marks and 17,088 simulated fills. Eighteen truncation checks passed. The main implementation also reconciled fee, price concession, gross, closed and estimated terminal P&L. The first verification run caught a missing reference check for costs consuming drawdown headroom between same-open entries. The reference was corrected and a regression test added. The registered rules and data were preserved. The local suite passed 130 Python tests, 36 website tests, the synthetic baseline and browser checks at 320, 390 and 1440 px. GitHub Actions attach to the draft review head.

There is no eligible v0.9 candidate. Preserve the independent prospective window from 1 January 2027 to 1 January 2028 UTC. The next research stage should first establish executable spot costs and admissible data. Consider a separately registered trend experiment only with a clear minimum sample plan and a clean evaluation window. Execution remains disabled.
