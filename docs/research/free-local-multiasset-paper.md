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
