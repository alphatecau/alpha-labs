# Alpha Labs — project status (5 November 2026)

**Scope:** deterministic research infrastructure and a standalone mobile operator UI. Financial release and execution remain disabled.

## Implemented and reviewed

- Offline long/flat EMA(12,48) baseline, passive comparison, modelled fees/slippage, strict CSV/UTC/quote validation and historical walk-forward diagnostics.
- Binance monthly spot BTCUSDT/ETHUSDT/SOLUSDT ingestion with archive checksums, exact hourly-grid checks, explicit early-close anomaly records, source-to-curated CSV binding, frozen local experiment records and a complete evidence exporter.
- Multi-year research with unsealed chronological partitions, 48-hour embargoes, doubled-cost stress, descriptive risk metrics, replay parity and optional operating-expense assumptions.
- Standalone mobile operator/advanced research UI and a fixture-tested read-only local research bridge. Integrated production backend/deployment is not verified.

## Evidence accepted

The complete uploaded 325-file package passed inventory and source-code checks against research implementation commit `6c95ddebbba1ea858372261da8ac87575133a8b8`. All three reports reproduced, including separate ledger comparisons. The selected April 2023–December 2025 window contains 99 source months and 72,432 hourly observations. January BTC is complete; March BTC has the confirmed early-close/missing-hour defect and remains excluded/rejected.

The frozen EMA baseline **fails the economic promotion screen**: BTC −11.012%, ETH −0.709%, SOL −7.346% in the final unsealed test partitions, all below matched-initial-allocation passive hold. Results use assumed costs and zero assumed operating expense, are denominated in USDT, and are not actual fills or AUD returns.

See [the completed evidence audit](docs/25_MULTYEAR_EVIDENCE_REVIEW_20261105.md) and [machine-readable findings](docs/evidence/2026-11-05_REPRODUCTION_AUDIT.json).

## Verification

102 Python unit tests and 36 website tests passed for the reviewed implementation; both PR workflows passed at that source commit. CI must pass again on each integration commit. The separate received-data audit reproduced three full reports and passed 27 NAV/fee/order-count comparisons plus nine sampled same-provider REST OHLCV comparisons.

## Outstanding

- Gate 1 is **partially evidenced**, not fully cleared: venue/account eligibility, permissible dataset usage, independent venue price checks, historical publication-time reconstruction and executable bid/ask/cost calibration remain unverified.
- Untouched prospective evaluation, statistical uncertainty, selection/multiple-testing adjustment, capacity analysis and a profitable candidate have not been established.
- Most API, worker, accounting, independent risk and execution services remain planned scaffolds. Operational paper trading, 24/7 supervision, broker/wallet signing, actual trading and production backend deployment are not implemented or verified. Backend/security workflows and the release verification script remain disabled/stubbed.

## Next stage

Integrate the reviewed research infrastructure after current CI passes. Register the Strategy Research v0.8 regime-filtered momentum hypothesis and its falsification/candidate budget before evaluation; preserve EMA(12,48) as the frozen comparator. Complete the remaining source/cost prerequisites before promoting any candidate. No paper/live bot, broker connection or capital release is approved by this engineering review.

## v0.12 additive draft — 7 November 2026

Main baseline `9d705bd` and PRs #9–#11 were audited before implementation. Development is isolated on `development/global-foundation-v0.12`; no research branch was merged. The prior research/strategy failures remain preserved.

Implemented locally: opaque development-token identity and tenant/role checks; immutable causal quote/proposal contracts; fourteen recorded deterministic committee roles; fail-closed real-strategy gates; transactional simulation risk checks; durable market/marketable-limit/partial/reject/cancel/fill lifecycle; long inventory, adverse stop-gap exits, journal replay, persistent HALT and backup/restore; responsive authenticated local dashboard. No actual language model, market feed, customer registration, managed secret service or broker order transport is connected.

Global commercial beta remains **NO-GO**. Hosted auth/MFA/passkeys/recovery, process-isolated risk authority, licensed feeds, empirical strategy/execution validation, equities integration, distributed load/security, customer billing/privacy/regional legal review and physical device acceptance remain incomplete or unverified. See `docs/v0.12/` for exact scope, evidence and remaining gates. Existing backend/security scaffolds are not represented as operational services. Live trading, capital release and production deployment remain disabled.
