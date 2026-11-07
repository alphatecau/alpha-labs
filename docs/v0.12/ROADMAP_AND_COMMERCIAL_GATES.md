# v0.12 → v1.0 implementation roadmap

Dates and costs are not committed. Stage promotion requires evidence, not a feature-count target. Current beta decision: **NO-GO**.

| Priority / stage | Deliverable | Dependencies / acceptance | Current status |
| --- | --- | --- | --- |
| P0 / A | Baseline, architecture, contracts, threat model and preservation | Reviewed main/PR9–11 pins; unchanged historical findings | COMPLETE for this increment |
| P0 / B | Committee and deterministic decision/risk boundary | Recorded fourteen-role cycle, negative authority and quote tests | PARTIAL: deterministic fixtures; real LLM/data/evidence absent |
| P0 / C | Durable autonomous simulation | Entry, partial/reject/cancel/fill/stop, journal replay, HALT, restart and backup | PARTIAL: synthetic spot slice implemented; empirical execution absent |
| P0 / D | Hosted identity and tenant security | Managed auth/MFA/passkeys/recovery, PostgreSQL RLS, service identities and external security review | BLOCKED for beta; local operator boundary implemented |
| P0 / research integrity | Resolve PR11 defects and review PR9–11 stack separately | Revised tests, immutable source/evidence links, frozen prior decisions, independent sign-off | Not merged or changed by v0.12 |
| P1 / source and costs | Licensed point-in-time quotes/trades/depth and observed cost evidence | Rights/eligibility, independent prices, arrival timestamps, raw custody, replay calibration | UNVERIFIED |
| P1 / isolated authority | Separate risk service and trusted evidence registry | Signed/expiring/one-use grants, anti-replay, independent policy owner, deny on outage | PLANNED; next engineering milestone |
| P1 / E | Equity/ETF research integration | Separately reviewed v0.11 stack, calendars, splits/dividends/delistings, currency and cost controls | PARTIAL on another branch; not included |
| P1 / broker sandboxes | Binance/eligible venue and IBKR adapter evaluation | Account eligibility, terms, market data rights, capabilities and observed lifecycle evidence | UNVERIFIED; no credentials requested |
| P2 / F | Commercial research/paper beta | Hosted auth/security/ops, accessible mobile onboarding, translations, billing consent, cost telemetry | BLOCKED; do not charge or invite users as a validated trading product |
| P3 / G | Independent conditional live assessment | Strategy evidence, execution calibration, risk/security, regional legal and operational acceptance | BLOCKED; no activation |
| P3 / H | Regional rollout | Explicit regional approval matrix, support, privacy, product availability and consumer obligations | BLOCKED; no globally enabled live feature |

## Strategy evidence gate

No true/false checklist or AI confidence score may grant strategy eligibility. A future evidence registry must bind experiment ID, frozen criteria, code/data/specification hashes, complete outputs, independent replay, calibrated costs/capacity, uncertainty/multiple testing, prospective custody, reviewer identity and review date to trusted external records. Keep failed numerical findings visible alongside missing evidence. New criteria cannot rescore v0.8/v0.9 or reuse the reserved prospective window for tuning.

## Regulatory/product review

Obtain jurisdiction-specific legal classification before customer launch, including research assessments and paper features; live capability is an additional gate. Determine advice/dealing/portfolio-management, custody, broker permissions, marketing/performance claims, privacy, consent, deletion/retention, data redistribution and local consumer obligations. Do not infer approval from a disclaimer, a broker API account or Australian residency.

Primary references inspected on 7 November 2026:

- [ASIC RG 255](https://www.asic.gov.au/regulatory-resources/find-a-document/regulatory-guides/rg-255-providing-digital-financial-product-advice-to-retail-clients): digital financial-product advice and Australian licensing considerations.
- [ASIC AFS licence requirements](https://www.asic.gov.au/regulatory-resources/financial-services/financial-advice/running-a-financial-advice-business/requirements-to-hold-an-afs-licence): financial services can include advice and dealing on a client's behalf. Exact product/business classification requires legal assessment.
- [SEC robo-adviser guidance notice](https://www.sec.gov/newsroom/press-releases/2017-52): automation does not remove applicable investment-adviser obligations.
- [IBKR paper-account limitations](https://www.interactivebrokers.com/campus/glossary-terms/paper-trading-account/): simulator/top-of-book/complex-order differences prevent treating sandbox fills as actual clearing or executable fills.

These references inform gates, not a legal opinion or jurisdictional approval. UK, EU, Asian and other regional assessments remain UNVERIFIED. Eligibility must be denied by default until a reviewed, versioned region/product/provider matrix is in force.

## Pricing and economics

| Proposed tier | Hypothesis in AUD/month | Before commercial use |
| --- | ---: | --- |
| Explorer | $0 | Define scanning/report/paper quotas and measured cost ceiling |
| Trader | $29 | Validate willingness to pay and cost of assessments, alerts and support |
| Pro | $79 | Meter committee/research/API usage, data rights and portfolio costs |

No billing, subscriptions, live entitlements or price approval are implemented. Determine actual infrastructure, database/backups, licensed data, inference, payments, support, tax and churn costs. Contribution per user = net subscription revenue − attributable data/inference/compute/payment/support costs. Break-even paid users = fixed monthly operating costs ÷ measured positive contribution. Actual costs, conversion, retention and churn are unknown, so no fabricated margin or commercial-viability estimate is supplied.

## Beta acceptance matrix

Verified here: local tenant predicates/roles, recorded fixture decisions, deterministic risk denial, durable synthetic lifecycle, reproducible cash and P&L, persistent HALT, simulated disconnect/recovery, causal quote negative tests and responsive browser flow. Still required: independent hosted isolation/security sign-off, approved point-in-time sources/strategies, empirical execution, production identity/secrets, multi-host/concurrent grant tests, observed SLO/load and recovery evidence, physical Android/iOS/accessibility, billing/privacy/legal assessment and reviewable CI on the exact draft head. Live and deployment flags remain false throughout.
