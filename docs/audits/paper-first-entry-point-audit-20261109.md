# Paper-first execution entry-point audit — 2026-11-09

## Scope and evidence

Reviewed `packages/alpha_lab/src/alpha_lab/research/paper_simulator.py`,
`paper_first_authority.py` and `paper_trading_session.py` on the research branch.
This is a targeted source review, **not** a repository-wide call-site audit.

## Findings

1. The legacy `PaperLedger.enable_simulation(operator_approved=True)` remains
   directly callable without consulting `TradingAuthority`. This is a
   **paper-authority bypass** for callers that instantiate `PaperLedger`
   directly. It is not a real-money execution route: the ledger has no broker
   network or order API.
2. The new `PaperTradingSession` is a fail-closed façade. It requires
   paper mode, emergency HALT cleared and explicit operator approval.
3. Live-copy readiness is descriptive only; all real-money execution remains
   unimplemented and disabled regardless of approval flags.
4. `PaperLedger` is an in-memory research scaffold; it is not durable,
   multi-tenant, authenticated or production-ready.
5. A user-owned broker account and user consent do not replace regulatory
   review, broker integration approval or independently verified performance.

## Required before website integration

- Inventory all direct `PaperLedger` call sites and block direct exposure
  from web/API routes; route new user-facing paper sessions through
  `PaperTradingSession`.
- Add server-side authenticated user/session ownership and isolation.
- Persist tamper-evident paper fills, with independent NAV reconciliation.
- Enforce per-user risk limits, idempotency, quote freshness and concurrency
  protection at the execution boundary.
- Verify browser/API requests cannot override mode, approval, HALT or risk
  controls.
- Add end-to-end negative tests and audit logging.
- Show live-copy as `DISABLED_NOT_IMPLEMENTED`, not as an available feature.

## Release decision

**NO-GO for production deployment.** Continue offline paper research only.
Do not merge, deploy, connect brokers or enable real-money orders.
