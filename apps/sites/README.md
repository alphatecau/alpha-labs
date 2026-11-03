# Alpha Labs operator dashboard — UI Sprint 001 (v0.6)

**Working responsive static website. No live market data, investment advice, exchange integration, wallet or orders.**

## Run

```sh
cd apps/sites
python -m http.server 8000
```

Open `http://localhost:8000/` in a browser. The app has no build step, CDN or external dependencies. It can be imported into a static website host / ChatGPT Sites with the **complete `apps/sites` folder** (including `advanced/`, the JavaScript files and stylesheet). It was not published to a live website in this sprint.

## Navigation

- Home: truthful research-mode portfolio and system state.
- Markets: BTC/ETH/SOL research watchlist, search, signal filter, instrument details.
- Intelligence: decision rationale, opposing evidence, independent trade rejection state and planned agents.
- Activity: decision / research / incident journal, category filter and demonstration-only CSV export.
- Settings & Advanced: synthetic preview toggle, source/permissions status, links to all preserved legacy research tools.
- Advanced: `advanced/index.html` retains the earlier seven sections, including functioning offline CSV research, backtesting and evidence experiments. A return link goes back to the new UI.

### Synthetic preview

In Settings, turn on **Research preview** to explore the intended visualisation. All sample numbers and decisions are entirely invented. A persistent **SYNTHETIC DEMO** banner is shown, and the demo is off on every reload. It never connects to a real trading account and cannot place an order.

## Tests

```sh
cd apps/sites
node --test tests/*.test.cjs
```

The existing long/flat offline JavaScript research engine and its regression tests remain unchanged. The Python v0.5 engine remains separate and is not connected to the operator UI.

For the Python foundation from the monorepo root:

```sh
PYTHONPATH=packages/alpha_lab/src python -m unittest discover -s tests/unit -p 'test*.py' -q
```

## Constraints / honest release status

**Implemented:** static UI routes, adaptive navigation, accessible labelled states, market search/filter, transparent synthetic preview, hypothetical portfolio curve, decision explanations, activity filtering/export, preserved legacy research workspace.

**Not implemented:** login/authentication, private user accounts, verified feeds, calibrated forecasts, real time websocket, risk-server integration, paper order management, live orders, independent long/short engine, operational PWA/service worker, remote server deployment. The frontend must not be exposed as a private authenticated account console without adding server-side authentication and authorisation.

The next UI integration sprint must connect authenticated read-only APIs and verified provenance before allowing the UI to claim any actual market state. Trade controls remain absent until the separate risk and execution-gate implementation is verified.
