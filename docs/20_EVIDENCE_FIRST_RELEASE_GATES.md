# Profit-first release gates — Alpha Labs

This programme serves one objective: **credible positive expected net economic value**, never guaranteed profitability.

## Gate 0 — implemented now
- Locally deterministic, cost-aware strategy baseline and passive comparison.
- Strict timestamp/quote unit/data validation and source checksums.
- No exchange login, no signing, no API or AI costs.
- This is NOT a research result on real prices.

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
Always report **modelled gross P&L**, **after-cost trade P&L**, and **after-operating-expenses P&L** separately. The current v0.5 CLI only computes the middle value under a simplified fee/slippage model and is **not** a sufficient basis for trading decisions.

## Agent token budget
Zero LLM tokens for ingest, indicators, backtest, risk, accounting, monitoring. Only introduce Condor/specialist LLMs for bounded research interpretation or anomaly review if no-AI ablation shows incremental value greater than cost.
