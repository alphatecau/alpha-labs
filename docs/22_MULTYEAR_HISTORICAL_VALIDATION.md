# Alpha Labs — Multi-year historical research, milestone 2

**Status:** executable research tooling, not approved live trading or validated profitability.

## Data source and boundaries

- Venue/data: Binance Vision public monthly **spot** BTCUSDT, ETHUSDT, SOLUSDT hourly klines. This is *not* an Australian broker, Solana DEX, or a derivatives/short-selling data set.
- Time: complete UTC calendar months only; default January 2023–December 2025 inclusive. Starting with Binance's January 2025 **spot** archive, open/close timestamps switch from milliseconds to microseconds.
- Each monthly ZIP is checked against its colocated published `.CHECKSUM` file, parsed with a bounded ZIP reader, and validated for every expected hourly candle, complete OHLCV, chronological order and exact timestamps. Any missing or inconsistent month fails; **no interpolation**.
- A CSV and manifest record dataset SHA-256, archive hashes and provenance. The checksum proves bytes correspond to those published by the archive provider, **not** independent market-price authentication.
- Raw, curated and experiment outputs are ignored by Git and remain on-device. The program requires network access to fetch archives. Source jurisdiction/terms/availability must be checked before using the data commercially.

Official source: https://github.com/binance/binance-public-data and https://data.binance.vision/ . Spot kline shape: `open time, open, high, low, close, volume, close time, quote volume, trades, taker buy base, taker buy quote, ignore`.

## Android / Termux

Run in a clean clone of the current repository, Python >=3.12 (stdlib only):

```sh
export PYTHONPATH=packages/alpha_lab/src
python scripts/multi_year_research.py fetch --symbols BTCUSDT ETHUSDT SOLUSDT --from-month 2023-01 --through-month 2025-12
python scripts/multi_year_research.py freeze --symbols BTCUSDT ETHUSDT SOLUSDT --from-month 2023-01 --through-month 2025-12
python scripts/multi_year_research.py evaluate --symbols BTCUSDT ETHUSDT SOLUSDT --from-month 2023-01 --through-month 2025-12
```

`run` combines fetch, freeze and evaluate for an initial engineering test, but sequential operations make it easy to stop if a download or checksum fails. Do not call a freeze generated *after looking at the data* an independent preregistration. Reports are written under `datasets/replay/reports/` with the first run refusing to overwrite a previous result. Raw archives can be reused for retries; if a run stops halfway, rerun `fetch`. Already completed CSV output is deliberately not overwritten.

Use `verify` to re-check the dataset/manifest hash. Use `--annual-overhead-usdt` to add an explicit per-market operating-cost assumption; 0 is the default **assumption**, not a real expense estimate.

## Method (all modelled; no broker execution)

1. Frozen long/flat EMA(12,48) signal. Decisions use **previous** completed hourly candle; fills are modelled at next hourly open.
2. Fixed 60% training / 20% validation / 20% test partitions, with a 48-hour no-trade embargo before validation and test. There is no parameter search or optimisation. Every partition starts with a fresh USDT 10,000 model balance, so partition returns are **not a continuous compounded portfolio return**.
3. Replays both EMA and same-initial-allocation passive buy/hold; estimates next-open 10 bps fee + 10 bps adverse slippage each side (config frozen), and tests 2× fees/slippage.
4. Reports modelled order counts, turnover, fee/slippage impact, time in market, after-modelled-friction returns, passive excess, and optional overhead-adjusted result. Includes annualised return, volatility, zero-rate Sharpe/Sortino, max drawdown and Calmar with zero-volatility metrics as null. Uncertainty/statistical significance **not** calculated.
5. Requires parity between new NAV tracking and the existing `backtest.engine.replay` for final NAV, fee tally and modelled order count. Includes the existing `research.walk_forward.evaluate_windows` 720-hour initial/168-hour rolling-window diagnostics; each fold resets capital and is **not an independent strategy retraining or a continuous portfolio equity curve**. Tests cover time leakage and deliberate errors.

## Fail closed / limitations

- The test partition is **not independently sealed**: local reruns and iteration can contaminate it. Holdout figures are descriptive only, not demonstrated independent alpha. Do not tune on the reported test results.
- Backtest fills are **not executable quotes**. Missing: live bid/ask, impact, orderbook depth, variable slippage, partial fills, market outages, spread, adverse selection, position capacity and borrow/funding for shorts.
- A 20% allocation cap does not guarantee a 20% maximum loss or risk budget.
- USDT is the quote unit, not AUD. No USD/AUD FX, tax, borrowing, exchange restrictions or custody reconciliation.
- Crypto is continuous but hourly returns are autocorrelated/heteroskedastic; naive annualised Sharpe/Sortino have no significance interval. No statistical confidence claim, test-count adjustment or real-world expected profitability.
- Existing read-only dashboard and Python baseline remain unchanged. No keys, trade endpoints, agent inference or deployment are introduced.

## Acceptance checks

```sh
PYTHONPATH=packages/alpha_lab/src python -m unittest discover -s tests/unit -p 'test_*.py' -q
node --test apps/sites/tests/*.test.cjs
```

New tests create **synthetic local ZIP archive fixtures** and never make a network request. Live provider download and full multi-year dataset evaluation must be run on a network-connected device, then independently reviewed.
