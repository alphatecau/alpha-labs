# Alpha Labs owner-only paper staging

The proposed build provides a single-owner, cash-funded USD spot simulation for BTC, ETH and SOL. The original research site and evidence remain available. There is no broker connector or autonomous strategy execution in this entry point.

## Service contract

- Coinbase Exchange level-one books supply the bid, ask, displayed quantities, sequence and exchange timestamp. The Python service polls all three products independently of the browser. A crossed, indicative, regressed, unavailable or more than 10-second-old book blocks fills. Exchange and receipt timestamps are recorded separately.
- Manual BUY requires a stop below the current bid. BUYs use the ask plus 5 bps of simulated slippage. SELLs use the bid less 5 bps. Both charge a 10 bps simulated fee. Quantity is limited to the observed top-of-book size remaining for that side and sequence. These are fixed research assumptions.
- The independent risk engine checks 0.25% per-trade planned stop-loss, 1% aggregate planned risk and 1× gross exposure for new exposure. Cash cannot go negative and SELL quantity cannot exceed the open position. Planned risk includes simulated entry and exit costs. A protective stop can execute below its trigger during a gap. With valid data and while armed, a breached lot triggers a position reduction subject to available simulated depth.
- A 2% daily loss relative to the sampled UTC day baseline or a 5% drawdown from the persisted high-water NAV suspends fills. The daily suspension stays latched through that UTC day. Emergency HALT disables all fills. A restart requires manual re-arming, and a stale arm request cannot reverse a newer HALT.
- The existing SQLite journal commits fill, order identity and quote evidence together. Restart replays the journal. FIFO P&L independently reconciles cash, fees, positions and NAV at fresh bid marks. Chart samples are in memory and rebuild after restart.
- This staging design supports one provisioned owner and one service instance on its own mounted disk. The account identifier is fixed in the ledger. Multi-tenant rollout needs a separate reviewed account-provisioning and isolation design. An externally anchored checkpoint for detecting rollback of the full disk is a separate security acceptance item.

## Deployment preparation

After explicit approval, use a separate always-on Render Python web service in Singapore. Keep auto-deploy off, use the reviewed exact commit and attach a persistent disk at `/var/data`. Run one worker, use `/healthz` as its health check and leave the current probe service available.

```sh
python -m pip install . 'gunicorn>=23,<24'
umask 077 && exec gunicorn --bind "0.0.0.0:$PORT" --workers 1 --threads 4 --timeout 30 'alpha_lab.research.live_paper_api:create_app()'
```

Set `ALPHA_PAPER_DATA_DIR=/var/data`, a new non-identifying `ALPHA_PAPER_ACCOUNT_ID` and `ALPHA_PAPER_RELAY_KEY_HEX` in Render. Generate the relay key as 32 random bytes encoded as 64 lowercase hex digits. `RENDER_GIT_COMMIT` comes from Render and must be a full Git SHA. Place the same account ID and relay key in the approved Sites runtime, with `ALPHA_PAPER_API_ORIGIN`, `ALPHA_PAPER_EXPECTED_COMMIT` and the owner's verified Site-scoped `ALPHA_PAPER_OWNER_SITE_ID`. Use the runtime secret settings for the relay key. For the first authorised identity bootstrap, the signed-in owner can open the Site's `/api/v1/paper/identity` route while the owner pin is unset. It returns only that visitor's Site ID and closes after the pin is configured. Do not put key material into source or request logs.

The Site exposes a same-origin owner-only relay. The Python API binds its signature to the HTTP method, path, body digest, exact build SHA, account, timestamp and nonce. It rejects direct unsigned requests, reused nonces and changed requests. The public health endpoint returns the service mode and build SHA. Retain the existing PostgreSQL security branches and staging database. The owner-only journal uses its own disk.

## Staging acceptance

1. Read Render deploy metadata and `/healthz`. Confirm that the deploy, health response and Sites pin agree on the exact Git SHA. Check that public unsigned requests and forged headers cannot read or write paper state.
2. Verify native ChatGPT sign-in on the staged revision with the intended owner, a separate signed-in account and a signed-out browser. Test the Site's ingress strips forged identity headers and that cross-origin mutations are denied.
3. Verify all three real provider books from the Render instance. Record source sequence and exchange timestamp. Exercise a provider interruption and verify that the UI identifies stale books and orders fail closed.
4. Arm, submit a small BUY with a valid stop, retry its order ID, and SELL part of the position. Compare fills, cash, fees, FIFO P&L and equity to the journal. Confirm refresh, restart, HALT and loss suspensions. Confirm the ledger is on the mounted disk and test a backup restore and independent checkpoint policy.
5. Exercise the dashboard on physical Android and check that every visible balance, status and quote agrees with the authenticated API. Record CI checks for the reviewed exact commit and verify GitHub status is read-only.
6. Keep autonomous strategy execution disabled until independent strategy, accounting, recovery, risk and security acceptance has been recorded.
