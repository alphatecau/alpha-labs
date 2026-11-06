# Alpha Labs — project status (6 November 2026)

**Scope:** deterministic research infrastructure and a standalone mobile operator UI. Financial release and execution remain disabled.

## Implemented and reviewed

- Offline long/flat EMA(12,48) baseline, passive comparison, modelled fees/slippage, strict CSV/UTC/quote validation and historical walk-forward diagnostics.
- Binance monthly spot BTCUSDT/ETHUSDT/SOLUSDT ingestion with archive checksums, exact hourly-grid checks, explicit early-close anomaly records, source-to-curated CSV binding, frozen local experiment records and a complete evidence exporter.
- Multi-year research with unsealed chronological partitions, 48-hour embargoes, doubled-cost stress, descriptive risk metrics, replay parity and optional operating-expense assumptions.
- Strategy Research v0.8 offline runner with a single registered LONG/FLAT regime-filtered momentum candidate, stop-risk sizing, UTC loss suspensions, cost sensitivity and an independent reference replay.
- Standalone mobile operator/advanced research UI and a fixture-tested read-only local research bridge. Integrated production backend/deployment is not verified.

## Evidence accepted

The complete uploaded 325-file package passed inventory and source-code checks against research implementation commit `6c95ddebbba1ea858372261da8ac87575133a8b8`. All three reports reproduced, including separate ledger comparisons. The selected April 2023–December 2025 window contains 99 source months and 72,432 hourly observations. January BTC is complete; March BTC has the confirmed early-close/missing-hour defect and remains excluded/rejected.

The frozen EMA baseline **fails the economic promotion screen**: BTC −11.012%, ETH −0.709%, SOL −7.346% in the final unsealed test partitions, all below matched-initial-allocation passive hold. Results use assumed costs and zero assumed operating expense, are denominated in USDT, and are not actual fills or AUD returns.

See [the completed evidence audit](docs/25_MULTYEAR_EVIDENCE_REVIEW_20261105.md) and [machine-readable findings](docs/evidence/2026-11-05_REPRODUCTION_AUDIT.json).

## Strategy Research v0.8 decision

**FAIL. Reject the registered candidate for promotion.** The previously examined April 2023–December 2025 dataset was reverified. After base friction and a scenario overhead of 120 USDT per market/year, the final unsealed partition returned −2.463% BTC, −1.008% ETH and −3.808% SOL. All three lost money even at zero overhead. A second run reproduced all reports byte for byte. A separate implementation reproduced 72,432 target decisions and 291 ledgers. See the [v0.8 implementation and verification report](docs/26_STRATEGY_RESEARCH_V08.md).

## Verification

102 Python unit tests and 36 website tests passed for the reviewed implementation; both PR workflows passed at that source commit. CI must pass again on each integration commit. The separate received-data audit reproduced three full reports and passed 27 NAV/fee/order-count comparisons plus nine sampled same-provider REST OHLCV comparisons.

The v0.8 review branch passed 117 Python tests and 36 website tests locally, plus the existing three-width browser smoke test and synthetic baseline CLI.

## Strategy Research v0.9 decision

**FAIL across all six registered variants.** Completed v0.8 loss attribution, four-family research review, a frozen six-variant study and shared-cash research accounting. The four-hour breakout returned +1.724% net on the shared portfolio in the final historical partition and +0.903% at doubled friction. It passed neither the forward-fold nor the minimum-sample hurdle. A separate implementation reproduced 894 ledgers. See the [results, verification and next gate](docs/29_STRATEGY_RESEARCH_V09.md).

## Outstanding

- Gate 1 is **partially evidenced**, not fully cleared: venue/account eligibility, permissible dataset usage, independent venue price checks, historical publication-time reconstruction and executable bid/ask/cost calibration remain unverified.
- Prospective evaluation, capacity analysis and a profitable candidate are outstanding. The v0.8 block-bootstrap bounds are descriptive for previously examined data, with a fixed nine-comparison adjustment.
- Most API, worker, accounting, independent risk and execution services remain planned scaffolds. Operational paper trading, 24/7 supervision, broker/wallet signing, actual trading and production backend deployment are not implemented or verified. Backend/security workflows and the release verification script remain disabled/stubbed.

## Next stage

Keep the v0.8 and v0.9 candidates rejected. Establish admissible market data and executable spot costs before registering the next trend hypothesis. Preserve the reserved prospective window. Paper/live execution, broker connection and capital release remain outside this research stage.
