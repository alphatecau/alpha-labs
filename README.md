# Alpha Labs — evidence-first multi-market research

**Status:** v0.6 mobile-first operator dashboard implemented; v0.3 research workspace preserved under `apps/sites/advanced/`; offline Python research engine retained. This project does not provide financial advice, live trading, verified alpha or guaranteed profit.

## Run the first research pipeline (Android Codespaces-friendly)

Python 3.12+, no exchange account, API keys or AI tokens required:

```sh
python -m pip install -e .
python examples/generate_synthetic_candles.py
python -m unittest discover -s tests/unit -p 'test_research_foundation.py' -v
python -m alpha_lab.cli examples/SYNTHETIC_SOLUSDC_1h.csv --quote USDC --provenance synthetic --output research-output.json
```

The demo data is **synthetic**. This pipeline is only an engineering baseline for later independent strategy and execution research. See `docs/19_FIRST_EXECUTABLE_RESEARCH_SLICE.md` for assumptions and limitations, and `PROJECT_STATUS.md` for module status.

## Optional: fetch recent public market candles (internet-connected Codespaces)

```sh
python -m alpha_lab.data.adapters.kraken_ohlc --pair SOLUSD --minutes 60 --output solusd-recent.csv
python -m alpha_lab.cli solusd-recent.csv --quote USD --minutes 60 --provenance kraken-public-ohlc --output solusd-research.json
```

The source is Kraken centralised-exchange SOL/USD, **not** Solana DEX pricing. The API returns at most 720 candles and the importer drops the unfinished last candle, so this is a short data-pipeline check **not a valid proof of alpha**. The importer is read-only. Internet access to the exchange was unavailable in the build environment; only its parsing and validation were tested with fixtures.

## New Alpha Labs operator UI (v0.6)

```sh
cd apps/sites
python -m http.server 8000
# separately: node --test tests/*.test.cjs
```

The portable dashboard in this repository has a mobile-first research view at `/` and the original seven-section interface at `/advanced/index.html`. Its optional research preview uses labelled synthetic data. See `docs/ui/UI_SPRINT_001_COMPLETION.md`.

## Hosted Alpha Labs Site and research API

The [hosted Site](https://alpha-labs-intelligence.alpha-tec-au86.chatgpt.site) has its own Sites source repository. The published dashboard uses a same-origin GET to `/api/v1/research/results`. The Site Worker calls that one route on the existing Render staging service, checks its Git revision and report digest, and returns selected historical metrics. The source is the [reproduction audit](docs/evidence/2026-11-05_REPRODUCTION_AUDIT.json) for the unsealed EMA(12,48) test window. Each report revision fixes the input digest in Python. The portfolio, private account research and paper controls have separate access requirements.

The staging entry point is `python deployment/staging_probe.py`. Render supplies `PORT` and `RENDER_GIT_COMMIT`. Set `ALPHA_RESEARCH_TOKEN_EXPIRES_AT` on Render to a future Unix timestamp in seconds and rotate the shared credential before expiry. Store a dedicated random 32-byte lowercase hex value as `ALPHA_RESEARCH_TOKEN` in the Render and Site secret stores. Set `ALPHA_RESEARCH_EXPECTED_COMMIT` on the Site to the full deployed backend commit. Keep credentials out of client code. The service exposes health and authenticated report reads only. An unavailable file, mismatched digest or missing configuration makes the report unavailable.

Keep Render auto-deploy off during acceptance. The deployed staging entry point and the saved Site version can be rolled back independently. To revoke report reads immediately, remove the dedicated backend token. Publication of the public Site is a separate operation.

### Acceptance record (20 November 2026)

Site version 7 (source `1cbbe8509099a07369fb671308d20dd605d624b1`) was
published in deployment `appgdep_6b0008fa6bf481919cf279089e2407f4`.
Its Worker uses manual redirect handling, rejects non-200 upstream responses
and verifies the digest before rendering results. The free Render service
`alpha-labs` (`srv-dbop6f3bc2fs73cqfksg`) serves release
`91ce4ad54fb93956f4001df0b88e533dd59dcb85` from its existing deployment
branch. The entry point and evidence bytes match [PR #185](https://github.com/alphatecau/alpha-labs/pull/185).

The deployed health check returned HTTP 200 with trading disabled. Missing and
incorrect bearers returned 401. The authenticated response returned 200 and
matched all 13,608 audit bytes, with SHA-256
`e1f03b0caf41e86d90ba582465ab038a93ce9be09669adce3b4fac8692c3e06f`.
The research service returned 404 on the paper order path.

Through Sites service access, the published research relay returned 200 and the
expected Render revision. Chromium rendered the hosted page, scripts and relay
response using a TLS-verified test transport with the Site credential confined
to its own origin. At 320, 390 and 1440 pixels, all cards matched the source
strategy and passive returns and the audit timestamp. Modelled strategy returns
were −11.01% BTC, −0.71% ETH and −7.35% SOL. The unauthenticated cloud test
client received an edge 403. This check did not exercise a signed-in owner session.

Rotate the shared credential before 20 December 2026 at 08:37 UTC. After
rotation, check health, denial without credentials and exact bytes with the new
credential, then verify the hosted Site relay. Version 4 and Render commit
`0c129c6f09b9859b4464086bc97fd7f6215f9d49` are the pre-integration rollback points.

The local paper terminal and its crash recovery are covered by the unit suite.
The public research endpoint cannot serve personal portfolios or accept orders.
Hosted paper acceptance requires an authenticated owner, independently checked
session/tenant ownership and durable ledger storage with tested restore. The
existing free service has no attached persistent disk. Keep hosted paper disabled
until these checks have passed.

## Architecture boundary

* `packages/alpha_lab/src/alpha_lab/`: offline research contracts and future services.
* `apps/sites/`: existing portable ChatGPT Sites UI.
* `apps/api`, `apps/dashboard`, `apps/worker`, `infra/`: planned, not production.
* `docs/future`: real-money execution documentation only, no signing keys or live execution code.

No AI model is called in the hot path. No live wallet or market orders are possible.
