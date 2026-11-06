# Strategy Research v0.8

**6 November 2026 · FAIL · Reject candidate for promotion**

The registered candidate lost money on all three markets in the final unsealed historical partition, including with zero assumed overhead. Every market failed the net-return and walk-forward screens. Review the [BTC](evidence/strategy-v0.8/BTCUSDT.json), [ETH](evidence/strategy-v0.8/ETHUSDT.json) and [SOL](evidence/strategy-v0.8/SOLUSDT.json) reports.

## Registered experiment

The branch starts from `main` at `9d705bd1982396b19006b9abd3ec8b6a254f2972`, which includes the independently reproduced multi-year evidence. The working tree was clean on checkout. Registration commit `27d1c8fb1a10134b1231cb7b409da9367d7efe04` preceded the historical replay. The registry pins one candidate, the full parameter set, costs, risk limits, partitions, test budget and prospective rules. The runner verifies the registry SHA-256 and rejects replacement data. [Experiment registry](../configs/strategy-v0.8.json)

- **Target.** LONG requires the 24-hour EMA to be at least 0.5% above the 120-hour EMA, a rising slow EMA versus 24 hours earlier, a trailing 72-hour return of at least 1%, and hourly return volatility below 1.5%. All other conditions target FLAT. The classifier reports upward, downward, ranging, high-volatility and uncertain states. It first becomes eligible after the 144-hour warm-up.
- **Timing.** A completed candle determines the target at the following hourly open. Stop and suspension triggers also use completed closes. The entry open anchors modelled pricing and position sizing. Each replay uses a fixed parameter set and prior candles to warm features.
- **Data.** The exact audited Binance Vision spot CSV hashes match 99 selected monthly source ZIPs and their checksums. BTC, ETH and SOL each have 24,144 contiguous hourly candles. The older 324-entry inventory and inner archive hash also matched. The dataset spans April 2023 to December 2025 and has already been examined. [Prior source audit](25_MULTYEAR_EVIDENCE_REVIEW_20261105.md)
- **Partitions.** The fixed 60/20/20 development, validation and unsealed test segments use 48-hour gaps before validation and test. Forward diagnostics start after the development segment. Every 720-hour step begins with a 48-hour trading embargo, and the last fold is included if at least 168 scored hours remain. Fourteen folds per market reset cash and positions and reuse known earlier candles for indicators. Fold results are descriptive and share a market environment across assets.
- **Benchmarks.** Frozen EMA(12,48) and passive hold use the original 20% starting-capital allocation. FLAT earns zero. All share dates, starting equity and transaction-friction settings. The candidate's risk sizing generally produces lower exposure, so return differences compare portfolio outcomes with different exposure.

## Final unsealed test

15 June 2025 19:00 UTC to 1 January 2026 00:00 UTC, exclusive. Each standalone replay starts at 10,000 USDT and covers 4,781 hours. Candidate returns include the primary scenario overhead of 120 USDT per market/year. Benchmarks carry zero assumed overhead. The return and drawdown columns are percentages of starting or peak equity respectively.

| Market | Candidate | Candidate at 2× friction | EMA(12,48) | Passive hold | FLAT | Candidate max drawdown | Positive forward folds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BTC/USDT | −2.463% | −3.459% | −11.012% | −3.448% | 0% | 1.885% | 1 / 14 |
| ETH/USDT | −1.008% | −2.222% | −0.709% | +3.226% | 0% | 1.996% | 4 / 14 |
| SOL/USDT | −3.808% | −4.800% | −7.346% | −3.739% | 0% | 3.335% | 4 / 14 |

| Market | Closed trades | Profit factor | Expectancy per trade (USDT) | Annualised Sharpe | Turnover / start equity | Hours exposed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BTC/USDT | 56 | 0.393 | −3.228 | −3.400 | 6.331× | 25.12% |
| ETH/USDT | 60 | 0.919 | −0.588 | −0.281 | 6.852× | 34.66% |
| SOL/USDT | 62 | 0.425 | −5.085 | −2.529 | 6.961× | 32.65% |

Profit factor and expectancy use closed trades after transaction friction. Portfolio marks include estimated liquidation proceeds for open holdings. Sharpe uses hourly returns, zero risk-free rate and 8,760-hour annualisation. Undefined ratios are null in the JSON. Trade counts and Sharpe should be interpreted alongside dependence across time and markets.

All three markets failed at base and doubled friction after primary overhead and fell below FLAT. ETH also fell below EMA and passive hold. SOL fell below passive hold. The candidate cleared the 30-trade minimum in each market but produced fewer than seven positive forward folds in each. The single candidate is rejected and every tested scenario is retained.

## Cost and risk sensitivity

Base friction is 10 bps fee plus 10 bps adverse price concession each side. The fee is anchored to Binance's published regular-user spot rate. The price concession is a modelling assumption for spread and slippage. The 2× case doubles both inputs and resizes positions under the same risk budget. Operating costs are hypothetical, prorated at the end of each replay and charged only to the candidate. They affect scoring and do not enter the intraperiod risk marks. [Binance spot fee schedule](https://www.binance.com/en-AU/fee/trading)

| Market | Base friction, zero overhead | Base, 120 USDT/yr | Base, 360 USDT/yr | Half stop risk, base, 120 USDT/yr | 2× friction drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| BTC/USDT | −1.808% | −2.463% | −3.773% | −1.562% | 2.805% |
| ETH/USDT | −0.353% | −1.008% | −2.318% | −0.826% | 2.405% |
| SOL/USDT | −3.153% | −3.808% | −5.117% | −2.241% | 4.151% |

The candidate plans risk to a stop reference 4% below its entry open, including round-trip friction. It caps planned loss at 0.25% of equity per position and respects the 1% aggregate limit within each standalone single-position replay. The 0.125% sensitivity halves the planned budget. A 2% decline from the start-of-UTC-day mark suspends entries until the next day. A 5% drawdown from the high-water mark suspends entries for the rest of the replay. Exit fills use the next open after the trigger. BTC and ETH reached about 5.0%–5.1% drawdown in earlier 2×-friction periods, illustrating overshoot from hourly observations and next-open execution. These controls describe proposed research limits. A shared portfolio and independent risk authorisation are requirements for any future execution design.

## Uncertainty and prospective validation

The final partition provides 199 complete UTC days per market, or 14 full 14-day blocks by count. The seeded 4,096-resample paired moving-block bootstrap scores daily change in equity, less prorated candidate overhead, against three benchmarks per market. The one-sided lower percentile uses a Bonferroni correction across the nine comparisons. All nine descriptive lower bounds are below zero. Cross-market dependence, regime shifts, finite sample size and prior inspection limit inference.

The genuinely unseen window is reserved for 1 January 2027 00:00 UTC to 1 January 2028 00:00 UTC, exclusive. For any candidate admitted to prospective evaluation, freeze its registration, code, inputs and scoring before the start. An independent custodian should preserve timestamped inputs and hashes and release the complete year once, after it ends. A PASS requires the registered market-level economics, drawdown and sample screens, all nine paired lower bounds above zero, an external reproduction and execution-cost/data checks. Changes after viewing results require a fresh window. The v0.8 historical runner has only FAIL and INSUFFICIENT EVIDENCE outcomes.

## SHORT compatibility

The signal records trend direction separately from the LONG/FLAT target. Downtrend currently targets FLAT. A future short model requires an identified instrument and venue, point-in-time eligibility and borrow availability or perpetual funding, collateral and margin rules, fees, liquidation and gap behaviour, and independently authorised position and portfolio limits. Price, cost and accounting models must cover the short leg before any short is scored.

## Reproduce on Python 3.12+ or Termux

Place the verified `curated/` and `raw/` trees from the prior evidence bundle together under the data root. The older multi-year fetch script can also rebuild this root if the published files still match the pinned audited data. Use a fresh output directory for every replay.

```sh
export PYTHONPATH=packages/alpha_lab/src
python scripts/strategy_v08.py --data-root datasets --output-dir datasets/replay/strategy-v0.8
python scripts/audit_strategy_v08.py --data-root datasets --reports datasets/replay/strategy-v0.8
diff -rq docs/evidence/strategy-v0.8 datasets/replay/strategy-v0.8
make verify
```

## Verification record

| Status | Evidence |
| --- | --- |
| Completed | Research-only strategy, registry, risk/cost controls, three comparison reports, audit tool and review branch. The original EMA implementation, website files and historical research outputs were preserved. |
| Tested | Baseline 102 Python tests and 36 website tests. Review branch 117 Python tests (15 new), 36 website tests, the legacy synthetic CLI and browser smoke at 320, 390 and 1440 px. Two full historical runs returned byte-identical reports. A separate float-based implementation reproduced all 72,432 targets and 291 ledgers across partitions and forward folds, checking modelled costs, trade counts, drawdown and selected equity statistics. |
| Failed | All three markets failed the registered economic screen. The first signal-exit test fixture also triggered the modelled stop and was corrected. The first reference replay found an uninitialised risk variable in its own ledger before an initial entry. That was fixed, covered with the archive fixture and rerun. |
| Blocked | A prospective result is unavailable before the reserved window is complete and independently released. The separate dashboard scaffold has an empty navigation test stub and no npm test script. |
| Unverified | Physical Android Termux execution, independent venue authentication, historical exchange publication times, executable quotes, spread/impact/latency calibration, capacity, venue/account eligibility, USDT/AUD conversion and tax. Trading authority remains disabled. |

Local runtime used CPython 3.12.14, pytest 9.2.0, Node 24.22.1, npm 11.9.0, Playwright 1.64.1 and Chromium 153.0.8010.0 on Linux x86-64. The research scripts use the Python standard library. The default browser download returned an invalid archive, and the alternative package's helper could not set ownership in this environment. The original smoke checks passed using the extracted Chromium binary. The first GitHub write path lacked branch permissions, and the authenticated repository path succeeded.
