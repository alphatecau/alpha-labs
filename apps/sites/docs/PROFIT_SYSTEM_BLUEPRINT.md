# Alpha Labs v0.3 — Profit-System Blueprint
**Status:** proposed engineering architecture and offline demonstrator; no verified trading profits. Date: 2 November 2026.

## Executive decision

Develop an evidence-driven, unleveraged liquid-market research system first, starting with **SOL/USDC** as a *test market*, not a proven opportunity. Use ChatGPT to help produce and audit code and research protocols; do not use an LLM as an unrestricted live trade decision-maker. Make **no-trade** the default. Defer memecoin launch sniping, leverage, arbitrage and autonomous self-modification until independently verified evidence warrants increased complexity. Maintain the existing independent Q3# scope.

**Objective:** maximise expected net *economic* returns within risk and uncertainty constraints. Positive realised profit cannot be guaranteed. *Profitability = realised gross trading P&L − spread/fees/slippage/failed execution − infrastructure/market-data/AI expenses, and tax is reported separately.* Portfolio value may be expressed in USDC, but the Australian tax/reporting view requires verifiable AUD FX conversion at the relevant event time.

## Root-to-end audit and release requirements

| # | Stage | Failure mechanism | Corrective architecture | Production gate |
|---|---|---|---|---|
| 1 | Economic objective | Optimising win rate or gross returns | Net P&L in quote units and AUD, risk-adjusted net outcomes, capital-to-cost break-even | Economically meaningful result after overhead |
| 2 | Market choice | New-token manipulation, unexitable pools | Begin liquid, unleveraged spot; compare alternative markets only with evidence | Defined, tradable market universe and capacity |
| 3 | Alpha mechanism | Generic RSI/EMA rules lack advantage | Register economic hypothesis and explicit falsification before testing | Unique mechanism and measurable counterfactual |
| 4 | Data | Missing periods, look-ahead, survivorship, manipulated volumes | Market-event timestamp, received-at timestamp, source, symbol/mint, quality flags, immutable raw records | Point-in-time reproducibility and supplier provenance |
| 5 | Data acquisition | API outage, stale or partial coverage | Rate-limited adapters, caching, retries, dual-source comparison for critical observations | Measured coverage, uptime, freshness |
| 6 | Backtesting | Idealised fills and unnoticed accounting bugs | Previous-completed-bar decisions, next-open assumptions, independent ledger reconciliation, market-impact extensions | All invariants hold; documented limitations |
| 7 | Selection | Parameter and holdout overfitting | Fixed preregistered candidates, chronological training/validation/test, purged gaps, trial count registry | Independent sealed evaluation overseen by separate process |
| 8 | Statistical evidence | Small sample luck, nonstationarity | Uncertainty intervals, selection bias correction, regime variation, realistic post-cost comparator | Robust effect survives sensitivity and independent data |
| 9 | Execution | Backtest edge disappears in quotes | Record contemporaneous bidirectional executable quotes, latency, estimated fees, partial/failure conditions | Edge survives realistic fill simulations and cost stress |
| 10 | Risk and capital | Compounding losses and operational failures | Independent veto, max exposure, drawdown/daily stop, kill switch, no leverage initially | Fault injection and risk limit tests pass |
| 11 | Security and legal | Private-key leakage, unsigned/failed state confusion, inappropriate commercial advice | Isolated signer in separate later phase, least privilege, confirmation reconciliation, regulatory and tax review | Explicit live-capital approval and independent security audit |
| 12 | Production operation | Data corruption, hidden downtime, regime change | Immutable event logs, daily reconciliation, emergency stop, drift monitoring and manual promotion | Continuous paper operation and rollback/restore proven |

## Three autonomous domains — strict separation

**Research domain:** immutable observations, feature engineering, candidate experiments and statistical reports. Research can *propose* strategy versions but cannot execute or change risk limits.

**Risk domain:** deterministic and independent accept/reject controls. Default fail-closed on missing security evidence, stale feeds, price/capacity uncertainty, breached drawdown or bad accounting state. A hallucinated model output cannot override a veto.

**Execution domain:** research release is simulation-only. In later approved production, orders need idempotent client IDs, separate submit/land/confirm/finalize/expire states, cost attribution and reconciliation from authoritative on-chain records. No unsigned transaction is treated as a settlement.

## Evidence protocol to implement server-side

1. Register one hypothesis before dataset inspection: reason for persistence, symbols, venues, time horizon, rule, controls, exact rejection criteria, dataset-source metadata, expected trading costs.
2. Capture and hash the historical dataset and record every change, trial, configuration and code revision.
3. Create chronological train/validation/untouched test partitions. Include an embargo sufficient for label horizon; a one-bar demonstration embargo is not necessarily sufficient in production.
4. Tune only on training; choose the single candidate using validation under a documented score, after multiple-comparison controls. Prevent repeated test-set peeking using a locked server-side evaluation service.
5. Evaluate the selected rule once on the sealed holdout and disclose confidence bounds, benchmark, full costs, trade capacity, parameter sensitivity, regime performance and missing data.
6. Run a frozen forward paper strategy. Save rejected opportunities, trade signals, prevailing market state and contemporaneous executable route quotes; do not reconstruct a favourable price later.
7. Reject if costs, risk, missing data or uncertainty overwhelm the estimated edge. A positive paper return is *not* a live approval.
8. Require a separate capital pilot authorization with limited assets, audit-grade wallet infrastructure and regulatory/tax assessment; compare actual executions with forecast.

### Entry eligibility contract (future backend)

```
allow_new_position =
    data_verified_and_fresh
    AND instrument_and_venue_supported
    AND strategy_version_independently_approved
    AND forecast_net_edge_lower_bound > uncertainty_and_cost_buffer
    AND executable_route_capacity_sufficient
    AND independent_risk_veto == PASS
    AND no_kill_switch_triggered
```

If any critical term is UNKNOWN: `allow_new_position = false`. A Python or TypeScript service, not a prompt, enforces the rule.

## Avoid common research mistakes

- Backtesting the four toy candidates in this website demonstrates a *method* only. It does not constitute independent statistical verification or establish an edge. Repeating the holdout until it looks good invalidates its independence.
- A simple 60/20/20 split is a teaching tool. Production needs period diversity and horizon-aware purging / embargo, robust bootstrap-based uncertainty, multiple-testing adjustment, and measurement of trial count.
- Historical OHLCV values are **not executable trades**. They cannot prove slippage, orderbook depth or failed transaction rates. Both Jupiter route quotes and pool-state records require timestamped capture when implementing independent shadow mode.
- New SOL/USDC prices are usually measured in USDC. Do not report the resulting USDC portfolio equity as AUD, and do not assume USDC and USD/AUD conversion equals 1.
- Profit needs enough absolute return to cover hosting, APIs, occasional stuck positions and the cost of invested capital. A positive percentage return can still be negative operating profit.

## Implementation priority & conditional schedule

| Gate | Suggested work | Approximate target, assuming resources available |
|---|---|---|
| 0 | Lock economics, quote units, loss budget, market and experiment contracts | Week 1 |
| 1 | Historical data provider evaluation, source provenance, audited CSV schema | Weeks 2–3 |
| 2 | Accounting invariants, chronological replay, statistical analysis | Weeks 4–5 |
| 3 | Independent evidence review; stop if edge absent | Week 6 |
| 4 | Real-time shadow quotes, risk controls, replay parity, monitoring | Weeks 7–10, **only after Gate 3** |
| 5 | Paper-only hosted beta, recovery, reconciliations | Weeks 11–12 |
| 6 | Frozen forward evaluation and research decision | Weeks 13–16 **minimum** |
| 7 | Optional live-capital pilot — *separate, nonautomatic project* | After independent review; no guaranteed date |

The decisive gate is **week six**, not an arbitrary release date. If there is no evidence of after-cost alpha, halt expansion and reconsider the economic hypothesis.

## Verification matrix

Unit/contract/property tests; source freshness checks; cross-language numeric consistency; time-series leakage probes; portfolio accounting invariants; dataset tamper detection; stress with fees multiplied by 2; quote-vs-fill comparison; fault injection; security audit; baseline comparisons; measured false positives; cold-deployment and restore tests. All findings are linked to dataset hash, code revision, strategy version and source confidence.

## References (official or academic, checked 2 November 2026)

- Solana RPC: https://solana.com/docs/rpc — shared public endpoints are **not for production**.
- Jupiter Swap API: https://dev.jup.ag/docs/swap/order-and-execute (verify current reference before implementation; example route docs: https://github.com/jup-ag/docs/blob/main/swap/order-and-execute.mdx).
- Overfitting: Bailey et al., *The Probability of Backtest Overfitting*, https://escholarship.org/uc/item/4w1110bb ; Bailey & López de Prado, *The Deflated Sharpe Ratio*, https://doi.org/10.3905/jpm.2014.40.5.094.
- OpenAI API token pricing & prompt caching: https://developers.openai.com/api/docs/pricing and https://developers.openai.com/api/docs/guides/prompt-caching .
