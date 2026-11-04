# Alpha Labs — TradingAgents Research Integration

Status: PLANNED — NOT IMPLEMENTED
Scope: Research, backtesting and risk management
Live trading: DISABLED

## Objective
Adapt the research architecture of
TauricResearch/TradingAgents without replacing
Alpha Labs' deterministic backtesting engine.

## Phase 1 — Strategy Research
- Regime-aware momentum
- Trend, volatility, RSI and MACD analysis
- Matched-exposure passive benchmarking
- Preserve frozen EMA(12,48) baseline

## Phase 2 — Independent Validation
- Walk-forward evaluation
- Unseen out-of-sample data
- Fees, slippage and turnover analysis
- Drawdown and risk-adjusted performance
- Reject strategies without demonstrated value

## Phase 3 — AI Research Agents
- Technical analysis agent
- Bullish research agent
- Bearish research agent
- Independent risk-review agent
- Structured, auditable decisions

## Phase 4 — Market Intelligence
- Timestamped market news
- Sentiment analysis
- Fundamental and macroeconomic context
- Strict prevention of future-data leakage

## Phase 5 — Portfolio Research
- BTC, ETH and SOL correlation analysis
- Portfolio concentration limits
- Position sizing and exposure controls
- Portfolio-level performance evaluation

## Phase 6 — Continuous Improvement
- Record research decisions and outcomes
- Compare agents against deterministic baselines
- Measure incremental value after costs
- Reject unnecessary model complexity

## Non-Negotiable Controls
- No live trading without separate approval
- No AI override of deterministic risk controls
- No claims of validated profitability without evidence
- No modifications to frozen baseline results
- No look-ahead bias or test-set optimisation
- Preserve existing architecture and tests

## Acceptance Criteria
- Existing unit tests pass
- Frozen baseline remains reproducible
- New strategies evaluated independently
- Out-of-sample results documented
- Transaction costs explicitly modelled
- Risk controls independently verified

Reference:
https://github.com/TauricResearch/TradingAgents
