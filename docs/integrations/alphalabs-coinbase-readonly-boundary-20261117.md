# AlphaLabs Coinbase connector — read-only integration boundary (2026-11-17)

Status: DESIGN / NOT DEPLOYED. Research-only. No live execution approval.

## Decision
Retain `coinbase_paper_book.py` and `PaperMarketFeed` as the sole executable paper quote reference. The AlphaLabs connector is a ChatGPT-scoped authenticated tool, **not** an automatically available Termux or Render API. Never assume connector credentials or capabilities can be forwarded into GitHub, Render, Termux or the application.

## Trust boundary
Connector read calls permitted for research ingestion: `coinbase_products_get`, `coinbase_products_candles`, `coinbase_products_book`, `coinbase_products_best_bid_ask`, `coinbase_fees`; optional account reconciliation `coinbase_portfolios_list/get`, `coinbase_balance`, `coinbase_orders_list/fills`. Keep account snapshots private and out of CI, logs, public dashboards and Git.

Deny all connector actions capable of creating, editing, cancelling or closing orders; moving/converting funds; paid x402 requests; portfolio mutations. Preview actions are not required. Do not install or configure any execution API credentials.

## Data contract for future import
Use a deliberately offline, explicit import of an operator-reviewed JSON snapshot, **not** a live connector relay. Each record requires schema version, provider, product_id allowlist (BTC-USD, ETH-USD, SOL-USD), product_type=SPOT, quote_currency=USD, observed_at UTC, source_exchange_at UTC where supplied, collection_time UTC, timeframe (4h/1d), candle start/end, OHLCV decimal strings, completeness flag, provider response status and provenance digest. No account IDs, personal holdings, OAuth tokens, API keys or raw HTTP headers. Reject unknown fields, missing timestamps, duplicate candles, non-finite/negative prices, high<low, inconsistent OHLC, stale or future observations, incomplete candles and insufficient lookback. Do not silently fill missing candles.

Research indicators must use only **closed** candles; compute EMA12/48 with documented warmup, Wilder RSI14, ATR14 and rolling volume; use deterministic Decimal parsing. Compare Coinbase connector observations with public Coinbase feed only as a research sanity check. Do not replace exchange timestamp/sequence verification, and do not treat the connector order book as executable without an independently reviewed adapter.

## Existing controls remain authoritative
- `local_paper_terminal.py`: startup HALT, explicit arming, isolated working directory, stable order IDs.
- `paper_risk.py`: planned loss <=0.25% equity; aggregate stop-risk <=1%; daily loss suspension 2%; drawdown suspension 5%; 1x notional ceiling.
- `paper_journal.py`, `local_paper_recovery.py`: exclusive SQLite writer, hash chain, replay and independent checkpoint.
- `dual_source_paper_gate.py`: optional separate research gate, opt-in until physical Android acceptance.
- Simulated paper balances are distinct from actual Coinbase balances.

## Acceptance checklist
1. No new runtime dependency on AlphaLabs MCP, OAuth, API keys or Coinbase account access.
2. Offline fixture tests: valid closed 4h/daily series, stale/future, malformed, duplicate, missing, incomplete and crossed books; schema and provenance checks.
3. Assert that missing/failed connector data returns UNVERIFIED, never cached VERIFIED, and does not arm or submit paper orders.
4. Validate cost assumptions (maker 9bps/taker 10bps reported on 2026-11-17, plus conservative slippage) without assuming fees remain constant.
5. Verify original public-feed paper path unchanged, restart/replay, no journal writes on rejected orders, independent HALT, and synthetic ETF isolation.
6. Run exact-head offline CI, networked smoke, physical Android 15 Termux and journal backup/recovery tests.
7. Security review: no secret leakage, no account snapshot in public artifacts, no connector write calls, no executable trading route.
8. Explicit separate authorisation is required for any future integration that could place real orders.

## Known limitation
This document is the safe first-stage implementation contract. It does **not** claim a functioning connector-to-runtime bridge, tested deployment or production readiness. No capital may be traded.
