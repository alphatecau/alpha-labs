# Alpha Labs v0.5 — first executable research baseline

**This is real, locally executable research software but not market evidence.** It never accesses a network, starts agents, stores keys, connects wallets, or places trades.

## Android-friendly usage (GitHub Codespaces, Python 3.12+)

```sh
python -m pip install -e .
python examples/generate_synthetic_candles.py
python -m unittest discover -s tests/unit -p 'test_research_foundation.py' -v
python -m alpha_lab.cli examples/SYNTHETIC_SOLUSDC_1h.csv --quote USDC --provenance synthetic --output research-output.json
```

For own CSV input use strictly continuous fixed-interval UTC OHLCV rows with header `timestamp,open,high,low,close,volume`. Specify quote units explicitly (USD/USDC/AUD/USDT/EUR). No FX conversion or data-source authentication.

## Contract and risk constraints

* Frozen EMA(12,48) directional baseline: long when fast EMA > slow EMA at preceding **completed** candle close; enter/exit at following candle open. No future values in the signal.
* One long-only asset, no leverage, at most 20% *initial balance* allocated per trade (configurable; this is NOT a 0.25% stop-loss or risk guarantee).
* Cash and inventory tracked with Decimal. Model adverse slippage and fee on both entries/exits; max drawdown on cost-adjusted portfolio liquidation estimate. Realised modelled order fees are reported separately from the **estimated future exit fee** included in current NAV.
* Chronological 70% training, 30% holdout, with warmup; the holdout is **not sealed** against researcher iteration yet. It must not be used for repeated tuning.
* A buy-and-hold benchmark uses the same 20% allocation and the same cost model. An explicit 2× fee/slippage stress scenario is included.
* The final open position is marked at last **close** with hypothetical conservative exit costs, not a confirmed market fill.
* Reported P&L is in **quote currency**, never automatically AUD. No profitability conclusion can be drawn from synthetic data or unverified imported CSV.

## Explicitly deferred

Verified paid/free historical datasets, contemporaneous executable quotes, spread/depth, latency, outages, order-rejection/partial fills, venue minimums, portfolio correlations, volatility sizing, statistically sealed testing, multiple-testing correction, operating expenses, AUD FX, paper execution engine, independent signing controls, real-money pilot, AI swarm.

## Next evidence gate

1. Establish approved data provenance and venue selection for BTC/ETH/SOL.
2. Capture trustworthy historical candles and real-time quotation evidence.
3. Write a separately pinned immutable research specification and untouched evaluation manifest.
4. Improve fill and cost model using real observations. Only then judge historical economic viability.

## Read-only public market ingestion (fixture-tested only)

Use the Kraken public OHLC adapter in an internet-connected Codespace to get recent BTC/ETH/SOL USD candles. It explicitly removes the unfinished final candle and records a SHA-256 manifest. Official Kraken documentation limits the endpoint to 720 latest entries. Do not interpret these short-window results as a statistically reliable trading strategy.
