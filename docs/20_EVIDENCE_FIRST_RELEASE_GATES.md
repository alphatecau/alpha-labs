# Profit-first release gates — Alpha Labs

This programme serves one objective: **credible positive expected net economic value**, never guaranteed profitability.

**Current evidence (5 November 2026):** the selected Binance monthly spot datasets and three modelled reports have been independently reproduced; see [the audit](25_MULTYEAR_EVIDENCE_REVIEW_20261105.md). The reviewed infrastructure is suitable for research integration. Gate 1 remains partly open because venue/account eligibility, permissible dataset usage, independent venue checks, publication-time reconstruction and executable quote/cost calibration are not established. EMA(12,48) failed its economic screen and cannot be promoted.

## Gate 0 — implemented now
- Locally deterministic, cost-aware strategy baseline and passive comparison.
- Strict timestamp/quote unit/data validation and source checksums.
- No exchange login, no signing, no API or AI costs.
- Synthetic checks do not establish a result on real prices. The separate historical modelled results are documented in the audit and do not establish profitable alpha.

## Gate 1 — source-quality evidence
- Select one permitted venue and identify exact BTC/ETH/SOL spot pairs.
- Record asset identifiers, exchange names, timeframes, UTC source timestamps, provenance and permissible usage terms.
- Ingest authentic historical candles and capture executable bid/ask or DEX quotes.
- Validate missing periods, corrections, stale prices and dataset hashes.

## Gate 2 — alpha hypothesis
- Pre-register economics and candidate strategy definition *before* evaluation.
- Fit on chronological training windows, select on validation, unseal final holdout once.
- Report passive comparator, exposure-normalized net returns, costs, capacity, drawdowns and uncertainty.
- If all candidates fail, do not deploy bots.

## Gate 3 — operational shadow/paper
- Same frozen signals across backtest and stream, cost model calibrated against quotes.
- Independent risk enforcement and reconciliation; 24/7 monitoring with no hot-path LLM.
- Confirm no unintended orders and fail-closed outages.

## Gate 4 — separate financial-capital permission
- Only after statistically credible forward evidence, wallet/broker security, Australian regulatory review and explicit capital approval.
- Start with independently capped exposure, evaluate real fills and losses before scaling.

## Trading economics
Always report **modelled gross P&L**, **after-cost trade P&L**, and **after-operating-expenses P&L** separately. The legacy v0.5 CLI computes only the middle value under a simplified fee/slippage model. The multi-year pipeline adds an optional operating-expense adjustment, defaulting to a zero assumption. Full gross/net economics and real execution-cost calibration remain requirements; neither CLI is a sufficient basis for trading decisions.

## Agent token budget
Zero LLM tokens for ingest, indicators, backtest, risk, accounting, monitoring. Only introduce Condor/specialist LLMs for bounded research interpretation or anomaly review if no-AI ablation shows incremental value greater than cost.
