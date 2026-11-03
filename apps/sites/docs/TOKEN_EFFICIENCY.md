# Token-efficiency policy — v0.3

**Objective:** reduce AI token expenditure **without** reducing statistical reliability, operational safety or reproducibility.

## Core rule

**Zero LLM calls per routine market tick.** Price fetching, features, signals, risk decisions, order-state tracking and accounting use deterministic code. One AI request is allowed only for a predefined, high-value research exception after low-cost rules have filtered it.

| Tier | Workload | Default |
|---|---|---|
| 0 | Price feeds, indicators, backtests, transaction ledger, risk veto | Zero AI tokens |
| 1 | Daily batch diagnostics and experiment summaries | Local deterministic summaries first; optional small model |
| 2 | Ambiguous anomalies or failed validation diagnostics | Selected short structured AI call, deduplicated by event fingerprint |
| 3 | Major architecture/security change | Higher-capability model only on the scoped issue and relevant code diff |

## Execution policy

1. Fetch raw data once and cache it. Send only necessary *features and anomalies* to an AI, not candles, full repositories or repeated chat history.
2. Use schema-validated compact inputs and limited structured outputs. Typical per-review planning target: <=600 input tokens and <=150 output tokens; adjust only when justified. These are **targets**, not model limits.
3. Deduplicate events by `dataset_hash + strategy_hash + anomaly_code`; cache successful decisions with an expiry and provenance.
4. Group non-urgent reviews into batched jobs when provider discounts and latency requirements make this worthwhile. Cache stable prompt prefixes only when cache economics are favourable.
5. Configure per-day and per-month API spend caps, a hard per-request token cap, retries with backoff and circuit breakers.
6. Maintain a **no-AI control arm**. If additional AI costs exceed independently measured incremental net returns, disable that AI feature.
7. For development conversations use compact issue-specific tasks: changed files, exact errors, expected assertions, acceptance tests. Avoid whole-repository repetition. Prefer tests and diffs over verbose explanations.

## Example minimal runtime output

```json
{"event":"Q-128","status":"FLAG","risk_codes":["STALE_QUOTE"],"confidence":null,"reason":"Source latency exceeds configured limit"}
```

This should normally be produced by ordinary code without calling a model.

## Economic gate

`net_incremental_AI_value = observed_incremental_net_P&L - API_cost - added_latency_cost - new_operating_cost`.

Use **zero** AI calls unless the measured, independently verified incremental value is convincingly positive. The on-site calculator estimates token spend in **USD** from user-entered assumptions; the trading results stay in the quote asset (e.g., USDC) until a verified conversion is available.
