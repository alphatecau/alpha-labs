# Free API integrations — research-only release candidate

This branch adds a **standalone, read-only** Binance/CoinGecko price cross-check and a separate GitHub/OSV engineering workflow. It does **not** connect to order execution, enable live trading, or change risk approvals.

## Data sources and controls

- Binance: `https://data-api.binance.vision/api/v3/trades?symbol=BTCUSDT&limit=1` (also ETHUSDT/SOLUSDT). Public market-data host; no trading key.
- CoinGecko: `https://api.coingecko.com/api/v3/simple/price`, `include_last_updated_at=true`. Free public access may be throttled; optional free Demo key via `COINGECKO_DEMO_API_KEY` header. Never commit a key.
- Both observations must be no more than 300 seconds old, not over 30 seconds in the future, finite and positive.
- Price divergence above 5% fails closed. USDT versus USD is an imperfect comparison and may diverge for legitimate market reasons.
- Any HTTP error, malformed response, stale trade, missing CoinGecko timestamp, or unsupported asset returns `HALT`.
- The successful status is `VERIFIED_RESEARCH_DATA` **not** authorisation to trade. The checks do not guarantee exchange liquidity, execution quality, fair pricing, or profitable strategies.
- The Binance trade is a *recent executed trade*, not a current executable bid/ask. Do not use it to fill paper orders without separate bid/ask, fees, slippage, latency and market-hours rules.

## Run

```bash
PYTHONPATH=packages/alpha_lab/src python -m alpha_lab.data.dual_source_check --asset BTC
PYTHONPATH=packages/alpha_lab/src python -m unittest discover -s tests/unit -p 'test_dual_source_check.py' -v
python -m unittest discover -s tests/unit -p 'test_osv_audit.py' -v
```

Other supported assets: ETH and SOL. Each invocation uses two API calls; there is no polling loop or automatic fallback to fabricated data. Set `COINGECKO_DEMO_API_KEY` only in your local environment or an approved secret store if you use a Demo account. The CLI prints no credential.

## Engineering workflow

`.github/workflows/free-data-security.yml` runs deterministic, mocked, offline provider tests on pull requests. A separate weekly/manual job installs the project in an isolated GitHub runner, reads the current workflow's metadata via the GitHub REST API using a read-only token, and checks installed Python distributions against OSV querybatch.

A missing API response or unavailable OSV service fails the security audit rather than silently marking it passed. The OSV script reports vulnerability IDs, not secrets. The weekly job requires GitHub Actions to be enabled; it does not deploy code.

## Release gates

1. GitHub offline tests PASS on this branch.
2. Confirm public Binance and CoinGecko responses from the target network, including geographic availability and quota behaviour.
3. Verify paper-trading integration separately with deterministic risk HALT, replay and crash recovery tests.
4. Verify CI OSV audit and review findings before merge.
5. No production trading or order submission permitted.

Academic research APIs are intentionally deferred.

## Paper runtime integration boundary

`DualSourcePaperGate` is an opt-in wrapper for the existing `PaperMarketFeed`.
It exposes the same `poll`, `snapshot`, `start`, and `close` methods.
A caller can explicitly construct `DualSourcePaperGate(existing_feed)` and
call `refresh()` on a bounded background worker, not from an order-request path.
The wrapped `snapshot` reports BTC-USD/ETH-USD/SOL-USD unhealthy until all
required evidence for each product is validated. Evidence expires after 60 seconds.
An upstream feed HALT always remains a HALT. Provider errors never trigger orders.

**Not enabled by default:** The current paper market is Coinbase USD; the Binance
USDT/CoinGecko USD comparison is an independent research sanity check, not a
substitute for the existing Coinbase book, exchange timestamps or depth.
Activating the wrapper in the production paper service requires a deliberate
operator configuration, polling-budget design, device testing and acceptance
of cross-venue basis risk. Never enable it implicitly.

The `Manual public market provider probe` workflow can be started from GitHub
Actions by an authorised operator. It exercises the real public APIs, without
credentials or orders, for all three assets. CI does not automatically run this
network-dependent probe.
