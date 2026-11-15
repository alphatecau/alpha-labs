# Paper-trading execution-chain audit — 2026-11-16

Scope: code-level review of the existing local terminal, public market feed, dual-source
gate, paper risk, runtime, SQLite journal, recovery and authenticated research BFF.
This is **not** a full repository-wide or live-device acceptance certificate.

| Stage | Evidence | Finding |
| --- | --- | --- |
| Market data | `paper_market_feed.py`, `live_paper_quotes.py`, `dual_source_check.py` | Existing Coinbase public book remains the execution reference. Binance/CoinGecko check is separate, USD/USDT cross-venue research only. |
| Integration | `local_paper_terminal.py` | **GAP:** local terminal constructs `PaperMarketFeed()` directly. `DualSourcePaperGate` is not enabled in the CLI; do not claim independent cross-check protects its fills. |
| Validation | `paper_market_feed.py` | Existing feed uses `executable()` plus timestamp/sequence health checks; watchdog triggers HALT on bad feed. |
| Risk | `paper_risk.py`, `paper_runtime.py` | Position 0.25%, aggregate 1%, daily 2%, drawdown 5%, notional 1x; explicit operator and recovered-ledger gates. |
| Simulated fills | `live_paper_session.py`, `paper_runtime.py` | Simulation only; candidate fill is computed before durable append. |
| Journal | `paper_journal.py` | Exclusive writer, unique order IDs, contiguous hash chain, SQLite transaction and replay. Hash chain alone is not a trusted anti-rollback checkpoint. |
| Recovery | `local_paper_recovery.py` | Read-only snapshots, integrity check and independent replay; protected mode requires separate checkpoint authority. |
| Dashboard | `deployment/staging_authenticated_bff.py` | Authenticated read-only research endpoints; **not** proof of a live connected paper-terminal dashboard. |
| Concurrent gate refresh | `dual_source_paper_gate.py` | **DEFECT FIXED IN PR #135:** older completed refresh could overwrite a newer failure. Generation check and threaded regression added. |

## Required acceptance before claiming end-to-end readiness

1. Choose and document whether dual-source gate is **required** for local paper trading or remains an optional research monitor. If required, integrate it into CLI startup and a bounded background refresh loop with explicit HALT, provider quota and network-failure tests. Never invoke provider requests on order execution path.
2. Exercise market-data disconnect, stale/future timestamps, cross-venue deviation, malformed payload, rate limit, concurrent refresh, restart and fail-closed recovery.
3. Verify rejected orders leave journal unchanged; accepted simulated fills survive restart with same ID and replay state.
4. Run deterministic end-to-end tests through the actual terminal and dashboard read path, including unauthorised access and stale UI data.
5. Run the live public-provider smoke test from a networked runner, and the terminal on the physical Android/Termux target.
6. Keep real-capital execution disabled. Do not conflate CI success, paper simulation acceptance and live trading authorisation.

The tests on PR #135 passed for its head SHA `3f5bf6cbdae1397ab24651e03364ae7b305f4114`.

## Implementation update (same audit branch)

The CLI now supports `--dual-source-check` for Coinbase crypto paper mode only.
The opt-in wrapper polls the research providers on a separate bounded background
thread, propagates health updates to the session and expires evidence. Startup
remains HALT. Synthetic ETF fixtures reject this option.

Example (existing working journal only):

```sh
PYTHONPATH=packages/alpha_lab/src python -m alpha_lab.research.local_paper_terminal --dual-source-check
```

This does not activate live-capital trading, guarantee provider availability or
prove physical Android acceptance. Keep the feature opt-in pending device tests.
