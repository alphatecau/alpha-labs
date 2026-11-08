# Alpha Labs Phase 1 — Research governance and diversified trend preregistration
Date: 2026-11-08. Branch: `research/phase1-evidence-engine-20261108`.
**Research only.** No live trading, broker integration, deployment, merge, leverage or strategy promotion.

## Existing evidence and contamination
Week 2 final: https://github.com/alphatecau/alpha-labs/actions/runs/42472199571
Week 3 development: https://github.com/alphatecau/alpha-labs/actions/runs/42472475226
2023-04..2025-12 crypto development history and 2026-01..2026-10 crypto evaluation have both been inspected. They cannot be described as new independent holdouts. All prior hypotheses and failed tests remain in the experiment registry. Do not choose trend horizons or assets based on those returns.

## Frozen new hypothesis: diversified, medium-term time-series momentum
Hypothesis ID `P1-DIV-TREND-001`; status **PRE-REGISTERED, NOT EVALUATED**.
Markets: BTCUSDT, ETHUSDT, SOLUSDT spot (research only), and adjusted liquid US-listed ETFs SPY, QQQ, IWM, TLT, GLD, DBC, UUP (availability, licensing and complete history to be independently verified before use). ETF selection is a design assumption, not a proven point-in-time universe. Survivorship and fund inception must be handled explicitly. No synthetic ETF history, no forward-filled absent sessions.
Bar frequency: daily completed session closes, with UTC exchange-calendar alignment by market; decisions execute no earlier than next eligible session open. Crypto uses daily UTC; equities use official US exchange session dates, including holidays and early closes.
Predeclared trend signals: equally weighted 63-day and 252-day lagged total-return momentum, positive score => long; otherwise cash. Long-only. No shorts. Volatility estimate: 63 daily log returns, annualisation 365 crypto / 252 ETFs; target 10% annualised portfolio volatility, max gross exposure 1x, max asset weight 15%, maximum crypto sleeve 30%. Rebalance monthly on first eligible session after prior month-end; fees, spreads, slippage, liquidity caps and corporate actions modelled.
Baseline comparator: cash, risk-matched diversified buy-and-hold, and equal-weight eligible-universe benchmark; comparator exposures must be scaled ex ante using the same lagged volatility inputs and exposure caps. Report fees, impact, turnover, drawdowns and portfolio exposure.
Inference: record all strategy variants and datasets; no parameter search permitted under this protocol. Pre-specify 0.05 familywise error and correct across every registered hypothesis; block promotion without prospective independently sealed evidence and valid dependence-aware inference.

## Phase 1 engineering acceptance gates
- Independent replay of executed-order cash and positions, fees, and final liquidation NAV, separate from the simulator state.
- Gross-to-net trading-cost bridge with spread/fee/slippage separately and without counting embedded adverse price adjustments twice.
- Lagged, point-in-time, risk-matched benchmarks with no forward leakage.
- Immutable experiment identifiers, hashes, statuses and complete selection history.
- Causal timestamp and session validation; adversarial tests for duplicates, gaps, forged future bars, tampered orders, invalid fee fields and accounting mismatches.
- Do not claim market performance, legal compliance or independent portfolio risk authority until explicitly tested.
