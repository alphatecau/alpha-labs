# Live-data paper trading — staging gates (research only)

This branch adds a read-only Binance public bookTicker adapter for BTCUSDT, ETHUSDT and SOLUSDT, quote validation, age checks and estimated simulated costs. It does **not** wire an authenticated API, UI, automatic order placement, persistent multi-user ledger, websocket ingestion or staging deployment. PaperRuntime remains offline-only.

## Non-negotiable gates before integration
1. Public market-data GET-only transport with no account API keys; validate actual origin, TLS, response bounds and redirects before server exposure.
2. Exchange event timestamps or independent feed sequence/health verification. Local observation time is not exchange event time. HALT on disconnection, clock anomalies or stale quotes.
3. Keep paper order routing in the existing PaperRuntime and independent PaperRiskLimits; never invoke broker endpoints.
4. Map BTC/ETH/SOL to quoted USDT and convert to AUD using separately verified FX; do not label USDT balances AUD.
5. Use persistent, isolated account ownership and atomic journal/ledger updates; confirm restart replay and reconciliation.
6. Distinguish market/limit paper orders, partial fills, realistic bid/ask, fees and slippage. Do not promise executable fills.
7. Pass adversarial tests: stale feed, crossed book, duplicate orders, concurrent requests, quota exhaustion, HALT, tenant isolation, crash recovery.
8. Verify PR #93–#96 security branches and PR #97 CI baseline independently before deployment.
9. Independent staging acceptance, explicit operator approval and documented rollback. No live-money execution.

## Local checks
`PYTHONPATH=packages/alpha_lab/src python -m pytest -q tests/unit/test_live_paper_quotes.py`

No exchange credentials or live trading permissions are needed.
