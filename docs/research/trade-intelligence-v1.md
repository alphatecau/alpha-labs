# Alpha Labs Trade Intelligence Engine v1.0

This release provides read-only BTC/USD, ETH/USD and SOL/USD research. The live smoke checks and historical development replay returned **NO TRADE**. The existing independent promotion authority must approve exact strategy, version, direction, market, timeframe and regime evidence before the engine can present a sized research proposal.

## Repository reconciliation

| Component | Source reviewed | Decision |
| --- | --- | --- |
| Main and CI | `b9098035638d45fddd7dcbab9a784d034ad80def`, PRs #98 and #103, current workflows | Main has the initial public quote path and CI repairs. The main baseline passed 234 unit tests and 36 website tests. |
| Integration branches | PRs #104, #105, #106, #108, #109 and #111 | #104, #106, #108 and #111 landed on research targets. The draft uses the protected-state #109 head `509eee5185ff9b40a1d7a6d354b734ffb4d999fe` so the changes can be reviewed independently of its upstream integration. Nine workflows passed at that base. |
| Market data | `coinbase_paper_book.py`, `paper_market_feed.py`, bounded public HTTPS and `Bar` | Reuse exchange-timestamped Coinbase books and the public transport. Extend with complete four-hour and daily OHLCV, product increments and rate-limit handling. Keep the older Binance receipt-time quote path separate from research recommendations. |
| Strategies and evidence | Frozen EMA helper, `strategy_evidence.py`, promotion authority and prior research reports | Reuse causal EMA and the chronological uncertainty screen. Add five versioned rules and exact-regime evidence requirements. Keep existing promotion authority and historical records. |
| Paper and storage | `LivePaperSession`, `PaperRuntime`, SQLite event journal, PostgreSQL checkpoint authority and independent P&L reconciliation | Reuse the durable paper desk. Add a read transaction for proposed sizing. Continue using the existing event format, risk-policy fingerprint and protected checkpoint schema. |
| Identity and quota | `OwnerPaperBFF`, Auth0 OIDC, opaque sessions, verified proxy ingress, PostgreSQL owner checks and shared quota | Mount one same-origin owner-only GET route through the existing boundary. The route has no browser-supplied portfolio, evidence or order input. |
| Analyst roles | TradingAgents work in open PRs #75 and #102 | Use a deterministic advisory committee over the same evidence snapshot. External model calls are unnecessary for the v1 decision. |
| Dashboard | Private owner desk in `apps/sites/owner-paper` and public Alpha Labs Site | Add the research panel to the existing private desk. Public Sites metadata shows version 4. The existing Render health endpoint reported research-only with trading disabled and its recommendation route returned HTTP 404. |

## Data and decision flow

- The Coinbase worker caches only complete UTC candle windows. Four-hour candles aggregate four consecutive one-hour bars. Daily candles use the native endpoint. A one-minute publication delay keeps candles out of features until the expected availability time. UTC alignment, complete cadence, bounded prices and volumes, duplicate rows, price jumps, crossed books, exchange timestamps and source sequence are checked. An invalid or expired input yields a rejection. HTTP 429 honours `Retry-After`.
- EMA 12/48, EMA slope, 12-bar momentum, ATR 14 and a prior 20-bar channel drive the trend and volatility classifications. The rules cover EMA trend, momentum, channel breakout, range mean reversion and regime-conditioned decisions. The regime and advisory committee expose the inputs and reasons.
- Validation requires a matching market, timeframe, version, direction, trend and volatility record. The thresholds include at least 40 trades, at least three positive folds and a majority of positive folds, positive net expectancy and adjusted lower bound, positive stressed returns and benchmark excess, drawdown within 5%, costs within the evaluated envelope, and independent promotion. Spot short entries return `UNSUPPORTED`. Insufficient evidence returns `UNVERIFIED`, idle signals return `FLAT` and invalid safety inputs return `HALT`.
- Qualified alternatives are ranked only over comparable evidence windows and cost assumptions. The ordered criteria are adjusted net lower bound, net expectancy, drawdown, stability, volatility, quoted spread and displayed depth. This is a heuristic ordering. The response does not assign probability of success.
- Proposed long size uses Decimal, the current ask, rounded entry zone, stop, target, cash, expected entry costs and conservative post-entry equity. The independent risk limits are 0.25% planned loss per trade, 1% aggregate planned stop-risk, 2% daily-loss suspension, 5% drawdown suspension and 1× gross notional. Research sizing adds a 35% single-asset cap, 70% grouped BTC/ETH/SOL cap, and 10% displayed-ask depth cap. These are fixed research assumptions. Pending paper orders, an operator HALT, insufficient minimum order size or unavailable protected state block sizing. Each proposed size uses the same current portfolio, so alternatives must be reassessed individually before any order.
- Proposals expire at the next candle boundary. A qualified plan includes stop, target, net reward-to-risk, estimated fees and slippage, strategy invalidation and a six-bar holding limit. The independent execution path continues to use the existing manual paper controls. The recommendation code has no order or arming call. Automated paper execution is disabled.

Coinbase endpoints and contract details are documented in [product candles](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles), [product metadata](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-single-product) and [public REST rate limits](https://docs.cdp.coinbase.com/exchange/rest-api/rate-limits).

## Local use and authenticated integration

Run in a separate checkout on Python 3.12 or newer. This probe fetches public market data and runs without a paper journal.

```bash
PYTHONPATH=packages/alpha_lab/src:. python tools/trade_intelligence.py --live --timeframe 4h
```

Use `--timeframe 1d` for the daily probe. Both return market data provenance, reasons, and the research decision. Virtual balances and provider prices are denominated in USD.

For the private desk, compose the reviewed `create_owner_paper_application` with the existing protected `LivePaperSession`, verified Auth0 BFF, current owner, separate CSRF key and verified reverse-proxy CIDRs. Pass `candle_feed=TradeCandleFeed(timeframe="4h")` to start its background worker. Its same-origin `GET /api/v1/paper/recommendations` uses the existing owner session and shared quota. It refuses POST and query parameters, and serves `Cache-Control: no-store`. The desk loads the research panel only when configured. Portfolio, orders, journal recovery and emergency HALT use the existing private paper routes. Stop the candle worker and paper feed before closing the journal.

Keep the existing public Site separate from owner portfolio state. An eventual Site link should point to the separately authenticated desk after proxy-peer trust, durable storage, owner and non-owner acceptance and shared quotas are verified at the deployed URL.

## Reproducible quantitative evidence

The development replay evaluated 2,208 hourly observations per asset from 1 July to 1 October 2025 UTC. It evaluated ten scored folds per asset, with 64 bars of warmup, six-bar embargoes and purging of trade labels that could cross a fold boundary. A simulated entry uses the first hourly open after the completed four-hour signal becomes available. Intrabar stop/target conflicts resolve against the proposal. The tests use 40 and 80 bps modelled round-trip costs, hourly liquidation marks, same-window buy-and-hold and fold-level bootstrap with Bonferroni correction across 300 comparisons. The short diagnostics omit borrowing and funding. The walk-forward scope is four-hour signals and the development data is unsealed.

| Asset | Best observed long rule with trades | Trades | Positive folds | 40 bps | 80 bps | Passive |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| BTC | EMA trend | 2 | 1/10 | +0.25% | −0.55% | −11.78% |
| ETH | Channel breakout | 9 | 4/10 | +12.93% | +8.95% | +18.85% |
| SOL | Mean reversion | 7 | 1/10 | −8.06% | −10.62% | +13.98% |

These are compounded modelled returns across scored folds. Every strategy/direction comparison had fewer than 40 trades. The ETH breakout also had a negative adjusted lower bound and lagged its passive benchmark. There are no promoted strategies or executable fill claims.

```bash
trade_capture="$(mktemp -d)" && PYTHONPATH=packages/alpha_lab/src:. python tools/trade_intelligence.py --walk-forward 2025-07-01T00:00:00Z 2025-10-01T00:00:00Z --capture-dir "$trade_capture" > "$trade_capture/provider-report.json" && PYTHONPATH=packages/alpha_lab/src:. python tools/trade_intelligence.py --walk-forward 2025-07-01T00:00:00Z 2025-10-01T00:00:00Z --replay-dir "$trade_capture" > "$trade_capture/offline-report.json"
```

The [machine-readable evidence](../audits/evidence/trade-intelligence-v1.json) records the validated live observations, canonical capture hashes, quantitative results and acceptance outcomes. Offline captures are explicitly labelled and cannot become live recommendations. The 2027–2028 UTC reserved evaluation interval was excluded from both the capture and replay.

## Acceptance reproduction

```bash
PYTHONPATH=packages/alpha_lab/src:.:tests/unit python -m unittest discover -s tests/unit -p 'test_*.py' && node --test apps/sites/tests/*.test.cjs && python -m ruff check packages deployment tests tools/trade_intelligence.py && python -m bandit -q -r packages deployment tools/trade_intelligence.py -ll
```

The repository's disposable PostgreSQL workflows provision isolated databases for the integration suite. To run all collected tests in that disposable setup, use `PYTHONPATH=packages/alpha_lab/src:.:tests/integration:tests/unit python -m pytest --import-mode=importlib -q -ra tests`. The import mode distinguishes existing unit and integration modules that share a basename.

```bash
PYTHONPATH=packages/alpha_lab/src:.:tests/unit python tests/acceptance/protected_paper_recovery.py --postgres-bin /path/to/postgresql/bin && PYTHONPATH=packages/alpha_lab/src:.:tests/unit python tests/acceptance/owner_paper_browser.py --postgres-bin /path/to/postgresql/bin --chromium /path/to/chromium-headless-shell
```

The complete Python 3.13 run passed 625 tests and 300 subtests, including 47 integration tests with disposable PostgreSQL available. Python 3.12 also passed 565 unittest cases and 43 website checks. Chromium passed the 393 × 873 touch-viewport owner-desk rehearsal, including the research panel. Bandit reported zero medium or high findings and five low findings. The declared runtime dependency audit reported no known vulnerabilities.

Recovery uses temporary SQLite and disposable loopback PostgreSQL. It checks matched backup restore, stale authority rejection, interrupted commits, idempotent replay and persistent HALT. The full suite also covers account and tenant isolation, shared quotas, session revocation, duplicate and partial fills, order cancellation and insufficient funds.

## Release decision

| Capability | Decision | Required evidence |
| --- | --- | --- |
| Local research diagnostics | GO | BTC, ETH and SOL public books and closed candles, explainable signals, fail-closed decisions and owner endpoint tests. |
| Actionable research recommendations | NO-GO | Independently approved out-of-sample evidence on the exact strategy and regime, robust net-of-cost results and independent promotion. |
| Automated paper trading | NO-GO | Existing safety limits and sizing remain independent. An automatic candidate-to-order path requires a separately authorised acceptance cycle. |
| Staging | NO-GO | Verify proxy ingress, deployed Auth0 owner and non-owner sessions, shared quota, protected storage and actual Android/Termux operation. |
| Real-money trading | PROHIBITED | Research and simulated paper use only. |
