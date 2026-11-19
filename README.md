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

The [hosted Site](https://alpha-labs-intelligence.alpha-tec-au86.chatgpt.site) has its own Sites source repository. Its research integration uses a same-origin GET to `/api/v1/research/results`. The Site Worker calls that one route on the existing Render staging service, checks its Git revision and report digest, and returns selected historical metrics. The source is the [reproduction audit](docs/evidence/2026-11-05_REPRODUCTION_AUDIT.json) for the unsealed EMA(12,48) test window. Each report revision fixes the input digest in Python. The portfolio, private account research and paper controls have separate access requirements.

The staging entry point is `python deployment/staging_probe.py`. Render supplies `PORT` and `RENDER_GIT_COMMIT`. Store a dedicated random 32-byte lowercase hex value as `ALPHA_RESEARCH_TOKEN` in the Render and Site secret stores. Set `ALPHA_RESEARCH_EXPECTED_COMMIT` on the Site to the full deployed backend commit. Keep credentials out of client code. The service exposes health and authenticated report reads only. An unavailable file, mismatched digest or missing configuration makes the report unavailable.

Keep Render auto-deploy off during acceptance. The deployed staging entry point and the saved Site version can be rolled back independently. To revoke report reads immediately, remove the dedicated backend token. Publication of the public Site is a separate operation.

## Architecture boundary

* `packages/alpha_lab/src/alpha_lab/`: offline research contracts and future services.
* `apps/sites/`: existing portable ChatGPT Sites UI.
* `apps/api`, `apps/dashboard`, `apps/worker`, `infra/`: planned, not production.
* `docs/future`: real-money execution documentation only, no signing keys or live execution code.

No AI model is called in the hot path. No live wallet or market orders are possible.
