# Alpha Labs post-merge integration · 13 November 2026

## Baseline and pull requests

GitHub default branch is main at b9098035638d45fddd7dcbab9a784d034ad80def. The #103 squash commit and its PR head have identical trees. Fresh baseline execution passed 247 Python tests plus 48 subtests and 36 website tests.

| PR | Observed state | Commit and actual integration | Changed files and CI |
|---|---|---|---|
| [#103](https://github.com/alphatecau/alpha-labs/pull/103) | Merged | b9098035638d45fddd7dcbab9a784d034ad80def on main | [30 files](https://github.com/alphatecau/alpha-labs/pull/103/files) · 10 successful PR-head workflows including [backend](https://github.com/alphatecau/alpha-labs/actions/runs/43171222961) |
| [#104](https://github.com/alphatecau/alpha-labs/pull/104) | Merged into #103's branch | 9bdf0e82ac006e650c204e5eb597b968cb416b44. The merge commit has no ancestry path to main. | [137 files](https://github.com/alphatecau/alpha-labs/pull/104/files) · 15 successful PR-head workflows including [PostgreSQL](https://github.com/alphatecau/alpha-labs/actions/runs/43174500720) |
| [#105](https://github.com/alphatecau/alpha-labs/pull/105) | Open draft | Current inspected head 00344e448b2c5c71308a162979b37dd2c58a5a82. It includes #107, #108 and #106. | [98 files](https://github.com/alphatecau/alpha-labs/pull/105/files) · 19 successful workflows and one initial [ref-revalidation failure](https://github.com/alphatecau/alpha-labs/actions/runs/43246488473) at inspection |
| [#106](https://github.com/alphatecau/alpha-labs/pull/106) | Merged into #105's branch | 00344e448b2c5c71308a162979b37dd2c58a5a82 | [38 files](https://github.com/alphatecau/alpha-labs/pull/106/files) · 8 successful workflows including [checkpoint acceptance](https://github.com/alphatecau/alpha-labs/actions/runs/43241208694) |
| [#107](https://github.com/alphatecau/alpha-labs/pull/107) | Merged into #105's branch | c955c1ec5d0f1866e2bd988fb8eda7ba107b5ec4 | [6 files](https://github.com/alphatecau/alpha-labs/pull/107/files) · 8 successful PR-head workflows |
| [#108](https://github.com/alphatecau/alpha-labs/pull/108) | Merged into #105's branch | be2901e7582eee9636460236b2521b2fefe7a2c0 | [9 files](https://github.com/alphatecau/alpha-labs/pull/108/files) · 8 successful PR-head workflows |
| [#111](https://github.com/alphatecau/alpha-labs/pull/111) | Merged into #108's branch | 7292466cf287332f9accee43e1daf60f30b9e074. This merge followed #108's integration into #105. | [3 files](https://github.com/alphatecau/alpha-labs/pull/111/files) · 8 successful PR-head workflows |

The #105 audit log attributed its failure to repository refs changing during collection. The collector rejected the moving snapshot and wrote diagnostics. The read-only rerun after refs settled passed (job 131302653077). The current local candidate preserves that fail-closed collector. This repository scan observed 120 remote branches and 79 open PRs. Related historical branches and the newer dependency-bot PRs retain their own review scope.

The local candidate uses the reviewed local source at cfef52790c6905182e97ba4df1a72fef82e0b6b8 plus the three-file #111 delta. #109 and #110 are open drafts. They supply a stronger checkpoint protocol, order lifecycle and fixture profile than the older isolated terminal. #101 and the earlier #93/#95/#96 security branches remain useful historical references. The authenticated owner BFF, its PostgreSQL service and the Render manifests stay in their dedicated review stack. This candidate adds a terminal process with no listener or remote order route.

## Source-of-truth components

| Component | Candidate source | Integration |
|---|---|---|
| Terminal and recovery | packages/alpha_lab/src/alpha_lab/research/local_paper_terminal.py, local_paper_recovery.py | Source from #110 with explicit working path, stable order IDs and verified copying |
| Runtime and fill model | paper_runtime.py, paper_simulator.py, live_paper_session.py | Shared PaperRuntime and main's long-only ledger. Local risk and lifecycle source from the owner stack. |
| Risk and accounting | paper_risk.py, paper_accounting.py | Independent deterministic rules and FIFO reconciliation. Risk-reducing sells keep daily, drawdown and authorisation checks. |
| Market data | coinbase_paper_book.py, paper_market_feed.py, live_paper_quotes.py | Coinbase public level-one books. Binance book ticker has no exchange timestamp and is gated from the terminal. |
| Other data adapters | data/adapters and data/public_https.py | Bounded public transport for Coinbase, Binance and Kraken. CSV, DEX and Solana research inputs have no order authority. |
| Persistence and checkpoint | paper_journal.py, paper_checkpoint.py, local_paper_recovery.py | SQLite WAL/rollback sidecar checks, hash replay, single writer, optional injected checkpoint interface. Local release is unanchored by default. |
| Auth0 and PostgreSQL | deployment/oidc_verifier.py and deployment/verified_proxy_ingress.py on main. Dedicated hosted review at cfef527. | Existing minimal main verifier and proxy controls preserved. Owner BFF and tenant infrastructure tested separately. |
| Dashboard and deployment | apps/sites, existing published Site, existing Render health probe | Current publication and services were inspected read-only. The candidate changes no website, Auth0 settings or Render manifests. |

The risk limits stay at 0.25% planned per position, 1% aggregate planned stop-risk, 2% daily loss, 5% drawdown and 1× gross exposure. Local portfolio reporting includes virtual USD and disclosed simulated costs. The strategy paths remain research-only. Previous research established no defensible edge. The reserved 2027–2028 dataset was untouched.

See [security findings](local-paper-security-20261113.md) and the [acceptance matrix](local-paper-acceptance-20261113.md).
