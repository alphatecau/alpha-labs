# ADR 0005 — additive local simulation foundation

**Status: proposed in the v0.12 draft.** Baseline and research stack are pinned in `docs/v0.12/BASELINE_AUDIT.md`.

## Decision

Extend the existing standard-library Python package in `alpha_lab.paper`, with a separate local dashboard and an authenticated loopback API. Keep the offline research engine, historical findings, `apps/sites`, existing risk assessor and all open draft branches unchanged. Do not import PR #11's unauthenticated checklist as trading authority. Only `synthetic-contract-v1` over synthetic TEST/AUD can exercise order creation. Every real strategy remains rejected or unverified.

Use SQLite transactions as a single-host development storage adapter. Hold one write transaction across current-state risk authorisation and each fill/accounting update. Enforce an opaque-token tenant boundary at HTTP entry and tenant predicates in store operations. Agents have data-only contracts. Agent assessments, user JSON, quoted news and model consensus cannot supply an approval or policy override. The simulation authoriser recomputes all limits.

## Why

Main's working research code is reusable, while API/execution/accounting services are largely placeholders. Basing on main avoids implicitly merging the 21-commit research stack. A dependency-free slice can be run in Python 3.12 and Termux, tested with independent arithmetic, and reviewed without acquiring broker credentials or configuring hosting. A static dashboard consumes actual local API state rather than fabricated performance numbers.

## Consequences

- Research-only risk assessment remains distinct from the new simulation authority; historical PASS flags never authorise an order.
- Marketable limit and market entries, partial synthetic fills, cancellation, long inventory, stop-gap exits and event reconstruction are implemented. Resting limit books, exchange-native stops, shorts and actual venue fills are unsupported.
- Risk is independent of agent decisions **in trusted application code**, not an isolated operating-system service. A process/database administrator can alter it. Split authority into a separately authenticated service with an independent key/policy owner before beta.
- Opaque local operator tokens are not customer registration or production identity. No MFA, passkeys, recovery or customer credentials are implemented.
- No new backend framework, ORM, task queue or frontend build service is required here. Reassess FastAPI/PostgreSQL/managed identity for hosted multi-user beta after this boundary is reviewed.
- New CI validates software scenarios; it does not establish strategy profitability, external security sign-off or executable fills.
