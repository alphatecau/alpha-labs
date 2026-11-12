# Free local multi-asset paper trading — execution evidence (2026-11-12)

Branch: research/free-local-multiasset-paper-20261112. Draft PR #108. Not merged or deployed.

## Delivered
- Inspected and reused existing PaperRuntime, PaperJournal, LivePaperSession, PaperMarketFeed, Coinbase level-one book adapter, paper risk and accounting components.
- Added local terminal: no HTTP listener, no broker keys, no live orders; manual state, markets, arm, halt, buy, sell, backup and quit.
- Reused existing durable SQLite journal, restart replay, single-writer lock, order-ID uniqueness, risk HALT, fees and slippage for BTC-USD/ETH-USD/SOL-USD only.
- Added broad cryptocurrency, US equity/ETF and ASX equity/ETF catalogue. Every catalogue entry is UNVERIFIED/DISABLED; this is discovery only.
- Added unit tests for catalogue/order gating and CLI dispatch; dedicated CI workflow includes inherited paper runtime tests.
- Added local setup and operational documentation.

## Task-by-task disposition
1. Component audit: DONE (existing components inspected).
2. Local launcher: IMPLEMENTED; untested on device.
3. Persistence: REUSED existing SQLite journal; independently protected checkpoint/restore NOT IMPLEMENTED in CLI.
4. Live crypto feed: REUSED Coinbase three-product feed; real local network acceptance NOT TESTED.
5. US/ASX market adapters: NOT IMPLEMENTED; licensing and exchange calendars unresolved.
6. Simulated orders: REUSED existing BTC/ETH/SOL session; no new multi-asset order execution.
7. Risk: REUSED existing HALT, stop-loss, exposure and quote health; local adversarial CI pending.
8. Mobile dashboard: NOT IMPLEMENTED; terminal is text-only.
9. Automated tests: ADDED targeted tests and workflow; execution NOT VERIFIED.
10. CI/release candidate: WORKFLOW ADDED; no run returned for latest head at reporting; NOT RELEASE READY.

## Hard blockers
- Current-head CI results and independent review.
- Actual Android Termux execution and provider connectivity.
- Protected external checkpoint and restore validation.
- US/ASX data entitlements and adapter quality.
- Multi-asset currency conversion, corporate actions, exchange calendars, risk models and fee schedules.
- Dashboard/mobile acceptance.

## Guardrails
No merge, deployment, paid resources, secrets, broker execution or real-money trading. A catalogue entry must never be treated as a verified quote or executable paper market.
