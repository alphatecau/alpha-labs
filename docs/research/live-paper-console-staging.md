# Alpha Labs owner-only paper staging

The proposed build provides a single-owner, cash-funded USD spot simulation for BTC, ETH and SOL. The original research site and evidence remain available. There is no broker connector or autonomous strategy execution in this entry point.

## Service contract

- Coinbase Exchange level-one books supply the bid, ask, displayed quantities, sequence and exchange timestamp. The Python service polls all three products independently of the browser. A crossed, indicative, regressed, unavailable or more than 10-second-old book blocks fills. Exchange and receipt timestamps are recorded separately.
- Manual BUY requires a stop below the current bid. BUYs use the ask plus 5 bps of simulated slippage. SELLs use the bid less 5 bps. Both charge a 10 bps simulated fee. Quantity is limited to the observed top-of-book size remaining for that side and sequence. These are fixed research assumptions.
- The independent risk engine checks 0.25% per-trade planned stop-loss, 1% aggregate planned risk and 1× gross exposure for new exposure. Cash cannot go negative and SELL quantity cannot exceed the open position. Planned risk includes simulated entry and exit costs. A protective stop can execute below its trigger during a gap. With valid data and while armed, a breached lot triggers a position reduction subject to available simulated depth.
- A 2% daily loss relative to the sampled UTC day baseline or a 5% drawdown from the persisted high-water NAV suspends fills. The daily suspension stays latched through that UTC day. Emergency HALT disables all fills. A restart requires manual re-arming, and a stale arm request cannot reverse a newer HALT.
- The existing SQLite journal commits fill, order identity and quote evidence together. Restart replays the journal. FIFO P&L independently reconciles cash, fees, positions and NAV at fresh bid marks. Chart samples are in memory and rebuild after restart.
- This staging design supports one provisioned owner and one service instance on its own mounted disk. The account identifier is fixed in the ledger. Multi-tenant rollout needs a separate reviewed account-provisioning and isolation design. An externally anchored checkpoint for detecting rollback of the full disk is a separate security acceptance item.

## Disabled integration and operator prerequisites

The earlier HMAC-only `live_paper_api:create_app()` factory is disabled. Its adapter remains only for offline compatibility tests. It must not be used as an alternate order route. No service or hosted Site has been changed.

`deployment.owner_paper_bff.create_owner_paper_application` composes the existing reviewed `StagingResearchBFF`, a `LivePaperSession` bound to its pinned internal `oidc_...` owner, an independently supplied CSRF key and explicit verified proxy peer CIDRs. There is no module-level application or listener. The factory starts the read-only quote feed and a separate health/authority watchdog; shutdown must stop the feed before closing the journal. Existing research/auth routes remain available. Private dashboard assets are served at `/owner-paper/` only after durable session and current-ownership validation.

All portfolio, order and arm routes share the PostgreSQL account quota used by the research API. The authenticated same-origin, CSRF-protected emergency HALT is quota-exempt and reveals no portfolio/history. It cannot place an order. Order identity is enforced by a SQLite unique index on a generated JSON identity column; the existing exclusive writer lock remains mandatory. Session revocation/expiry or loss of account ownership halts the arming session through the watchdog. Dependency outages fail closed.

Before any owner-approved staging exercise, independently verify real Auth0/OIDC callbacks and cookies, the actual reverse-proxy trust boundary, restricted database roles, protected durable storage, backup/restore and independently authenticated journal checkpoint policy. Full-disk rewrite/rollback is not prevented by a hash chain stored on that same disk. The hosted ChatGPT Site identity integration and physical Android acceptance are still blocked. Do not deploy this proposal based on unit or CI results.

## Staging acceptance

1. Record the reviewed exact Git SHA. Verify the actual TLS/proxy boundary and durable OIDC session/current ownership checks. Confirm unauthenticated, wrong-owner and forged-header requests cannot read or mutate paper state.
2. Verify native ChatGPT sign-in on the staged revision with the intended owner, a separate signed-in account and a signed-out browser. Test the Site's ingress strips forged identity headers and that cross-origin mutations are denied.
3. Verify all three real provider books from the Render instance. Record source sequence and exchange timestamp. Exercise a provider interruption and verify that the UI identifies stale books and orders fail closed.
4. Arm, submit a small BUY with a valid stop, retry its order ID, and SELL part of the position. Compare fills, cash, fees, FIFO P&L and equity to the journal. Confirm refresh, restart, HALT and loss suspensions. Confirm the ledger is on the mounted disk and test a backup restore and independent checkpoint policy.
5. Exercise the dashboard on physical Android and check that every visible balance, status and quote agrees with the authenticated API. Record CI checks for the reviewed exact commit and verify GitHub status is read-only.
6. Keep autonomous strategy execution disabled until independent strategy, accounting, recovery, risk and security acceptance has been recorded.
