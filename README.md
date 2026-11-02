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

The main page at `/` is now the mobile-first Research-mode operator dashboard. The original seven-section research interface remains at `/advanced/index.html`. Use Settings > Research preview for clearly labelled synthetic interface data. The Python engine is not yet connected to the frontend. See `docs/ui/UI_SPRINT_001_COMPLETION.md`.

## Architecture boundary

* `packages/alpha_lab/src/alpha_lab/`: offline research contracts and future services.
* `apps/sites/`: existing portable ChatGPT Sites UI.
* `apps/api`, `apps/dashboard`, `apps/worker`, `infra/`: planned, not production.
* `docs/future`: real-money execution documentation only, no signing keys or live execution code.

No AI model is called in the hot path. No live wallet or market orders are possible.
