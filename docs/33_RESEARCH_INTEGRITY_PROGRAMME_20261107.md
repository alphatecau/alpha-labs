# Alpha Labs — Research integrity and multi-asset development programme

**7 November 2026 | Proposal on `research/multi-asset-v0.11` | Research only**

## Current evidence and constraints

- The accepted historical EMA baseline lost money after assumed costs on BTC, ETH and SOL.
- v0.8 rejected its registered regime-filtered momentum strategy.
- v0.9 rejected all six registered variants; the four-hour breakout returned +1.724% in the historical final partition but only 27 closed trades and 5/14 positive forward folds. Its lower adjusted confidence bounds were not positive.
- These periods are already examined. **Do not relabel them as untouched holdouts.**
- The reserved prospective window is 2027-01-01 through 2028-01-01 UTC. Do not use it for parameter tuning.
- v0.11 is an active multi-asset research branch; this document does not claim that its equities/ETF integrations are complete.
- No production execution, broker credentials, trading orders, or capital release is authorised.

## Priority workstreams and explicit acceptance

| Priority | Workstream | Deliverable | Evidence needed |
| --- | --- | --- | --- |
| P0 | Data custody and chronology | Immutable raw snapshots, UTC exchange/event/arrival timestamps, instrument identity, point-in-time corporate actions | Source hash manifests; adversarial timestamp and revision tests |
| P0 | Realistic costs | Venue-specific spread, fee tier, size/depth, latency and funding/borrow where relevant | Independent bid/ask/trade replay; cost-stress matrix |
| P0 | Research integrity | Registered hypothesis budget, chronological embargo, independent replay, multiple-testing adjustment | Frozen registration and independent report hashes |
| P0 | Risk authority | Separate position, exposure, stale-data and HALT policy | Negative controls; fail-closed tests; no execution permission |
| P1 | Strategy portfolio | Trend, cross-sectional momentum, rotation, mean reversion, pairs, carry as separate hypotheses | Each must be economically distinct and preregistered; reject when evidence insufficient |
| P1 | Prospective shadow ledger | Time-stamped decisions, simulated fills, rejected orders and drift | Forward-only immutable records; no live orders |
| P1 | Multi-asset adapters | Equities/ETF calendars, delistings, splits, dividends, symbol changes, currency conversion | Point-in-time data licence and adjustment tests |
| P2 | AI research committee | Structured bull/bear/sceptic evidence with citations | Incremental value over deterministic baseline after compute costs |
| P2 | Mobile dashboard | Read-only research evidence, data health and risk state | Authenticated API and Android acceptance |
| P3 | Commercial intelligence | Customer discovery for research analytics subscriptions | Customer validation and Australian regulatory review |

## Research promotion gate

`tools/research_promotion_gate.py` is a **standalone, offline evidence checklist**, not a statistical significance engine. Supply a JSON record containing `experiment_id`, `evidence` (each required field explicitly true only after independently verified) and `metrics` (decimal returns and drawdown, integer trades/folds). Missing or invalid evidence yields BLOCKED. Failing fixed illustrative thresholds yields REJECT. Complete records yield ELIGIBLE_FOR_INDEPENDENT_REVIEW, never live authorisation.

The initial numerical thresholds (positive net and doubled-cost return, positive adjusted lower bound, max drawdown <= 5%, >= 40 closed trades, >= 60% positive forward folds) are **provisional engineering gates**, not universal significance or optimality criteria. Before any future experiment, freeze the actual risk and statistical acceptance criteria with a power calculation, candidate budget and independent review. The `adjusted_lower_bound` input must be computed independently; the gate cannot validate its method.

Example invocation:

```sh
python -m unittest discover -s tests/unit -p 'test_research_promotion_gate.py' -v
python tools/research_promotion_gate.py /path/to/evidence-record.json
```

## Planned implementation stages

1. Reconcile `main`, v0.9 and v0.11 histories; preserve frozen experiment identities and audit the latest CI.
2. Extend point-in-time data contracts with market-specific calendar/corporate-action/quote semantics.
3. Build cost calibration and a separate deterministic independent replay oracle.
4. Preregister no more than a small fixed candidate family and freeze a test budget before running experiments.
5. Add prospective read-only shadow decisions with immutable provenance and independent risk rejection.
6. Evaluate AI only as a measurable incremental research component, not a replacement for evidence.
7. Add read-only operator dashboard integrations once authentication and source boundaries are verified.

## Release and security rules

No secrets in client bundles or GitHub. No unreviewed branch merge, production deploy, automated broker orders, signing keys or capital release. Never report simulated hardware, synthetic trading costs, backtests or AI-generated decisions as real executions. All missing provider data and incomplete validation must be labelled BLOCKED or UNVERIFIED.
