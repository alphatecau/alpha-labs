# Free local multi-asset paper trading — research branch

## Scope
This branch is an isolated, research-only foundation for an Android Termux or laptop-hosted, **single-user** paper trading terminal. It inherits the existing Alpha Labs paper journal, simulated accounting, risk HALT, Coinbase feed adapter and owner-only BFF research code from the integration branch. **No live brokerage orders, paid services, Render changes or credentials.**

The new catalogue covers a broad watchlist of cryptocurrency, US equities/ETFs and Australian ASX shares/ETFs. Every entry defaults to **UNVERIFIED / DISABLED**. An exchange listing is not evidence of a supported live feed.

## Market-data expansion requirements
- Crypto: BTC/ETH/SOL first, then additional pairs through provider-supported symbols; verify quote timestamp, instrument mapping, spread and fees.
- US: NASDAQ/NYSE/AMEX shares and ETFs; verify licensing, session calendars, splits/dividends, exchange halts, delayed vs real-time status and market hours.
- Australia: ASX shares and ETFs, AUD currency, exchange calendar and permitted market-data entitlements.
- Other exchanges, options and futures: separately gated, not silently presented as tradeable. Options require contracts, expiry, strike, right, multipliers and Greeks; futures require contract expiry and margin. Neither is implemented.
- Each new instrument requires verified adapter, paper fill model, fee schedule, venue clock, order-size rules, risk policy and persistence tests.
- All quote data must disclose live/delayed/stale status. Stale or unavailable quotes => HALT.

## Local-first acceptance gates
1. Test complete catalogue and unknown-symbol rejection.
2. Build a local launcher composing existing paper runtime with a persistent journal under a user-controlled directory and **independent** checkpoint backup; verify cold restart.
3. Connect verified provider adapters to crypto and shares, including realistic simulated costs and exchange hours.
4. Exercise order idempotency, risk HALT, feed loss, partial writes, recovery and no-broker execution.
5. Complete Android Termux smoke test; browser UI is optional for the first local milestone.
6. No merge/deployment without passing tests and independent review.


## Local terminal candidate (CI and Android acceptance pending)
The new alpha_lab.research.local_paper_terminal starts the existing Coinbase BTC-USD/ETH-USD/SOL-USD polling feed and the single-writer SQLite-backed LivePaperSession. It binds no HTTP port and contains no broker execution. Journal replay and startup HALT are inherited from PaperRuntime. All commands are manual.

Install Python >=3.12, clone this branch, and from the repository root run this single bundled command:

    python -m pip install . && python -m alpha_lab.research.local_paper_terminal --directory ~/.alpha-labs-paper

Commands: help, markets, state, arm, halt, buy BTC-USD 0.001 10000, sell BTC-USD 0.001, backup ~/separate-backups/paper.sqlite3, quit. Create a separate backup directory first. The session requires healthy, timestamped Coinbase quotes for ALL THREE products before arming. Network failure HALTs orders; every startup is halted until manually armed. Protective stop mandatory for buys. Existing fee, slippage, idempotency, risk limits and simulated fills are reused.

Caveats: A SQLite backup is NOT an independently authenticated checkpoint. The existing checkpoint support is not yet wired into the new launcher; independently protect and verify backups. No Android graphical dashboard or US/ASX quote integration. No provider availability guarantee. Local-only account binding must not be reused as hosted identity.

## Current readiness
Catalogue, CLI, targeted tests and CI workflow committed. Tests are NOT yet confirmed passed; physical Android Termux test not performed. Inherited runtime requires end-to-end local acceptance. All non-Coinbase instruments remain UNVERIFIED/DISABLED. No merge, deployment or real-money execution.

## Follow-up candidate · 13 November 2026

The terminal has two explicit USD profiles. Both use the same PaperRuntime, SQLite journal, order state, FIFO accounting and risk checks.

| Profile | Instruments | Data | Session policy |
|---|---|---|---|
| Default Coinbase spot | BTC-USD, ETH-USD, SOL-USD | Timestamped Coinbase Exchange public level-one quotes | All three books must be fresh and causal |
| --synthetic-etfs | SPY, QQQ, IWM, XLF, XLE | Deterministic synthetic quotes only | Explicit UTC windows, whole shares, no trades at or beyond the configured close |

The other catalogue entries are discovery-only. Live US and ASX quotes, corporate actions, FX conversion and additional crypto pairs require separate provider and data-quality acceptance. The fixture starts pre-open and advances when you type advance. On reopening, it starts halted and resumes at the last executed synthetic sequence if one exists.

From the root of the checked-out follow-up branch, start the local terminal on Termux or Linux with Python 3.12 or newer.

~~~sh
PYTHONPATH=packages/alpha_lab/src python -m alpha_lab.research.local_paper_terminal
~~~

For the separate offline ETF journal:

~~~sh
PYTHONPATH=packages/alpha_lab/src python -m alpha_lab.research.local_paper_terminal --synthetic-etfs
~~~

Type help for commands. In the ETF fixture, type advance, then arm. Submit limit buy SPY 2 100.50 90 --id sample_spy_limit_0001 for a partial fill at the fixture's displayed depth. Type advance again to match the remainder at the next book. A separate pending order can be cancelled with cancel ID. Use the same --id on a retry. Market orders require sufficient available top-of-book depth. Limit fills use the estimated price after slippage and observe the order's limit price. Fees are simulated separately. Remaining quantity persists until filled, cancelled or rejected. Reopening a journal always requires manual arming.

Fee and slippage default to 10 and 5 bps. Set --fee-bps and --slippage-bps for a new journal and use the same settings to reopen it. The journal pins market profile and cost policy. Keep separate profiles and policy versions in separate directories.

Backup publishes a verified SQLite copy in a separate existing directory. The local terminal has no independent checkpoint authority. Use private Termux storage for the journal and backup destination. A matching protected PostgreSQL restore is covered by the separate owner-staging rehearsal.
