# Alpha Labs

Private multi-market quantitative research project. **Development only: no live trading, verified profit, or financial advice.**

## Current verified release

Alpha Labs v0.6: responsive research-mode operator dashboard (Home, Markets, Intelligence, Activity), preserved Advanced research UI and offline Python research foundation. This GitHub repository currently contains a project bootstrap. **The full v0.6 source ZIP has NOT yet been imported into this GitHub repository.** Do not mistake the bootstrap for the runnable application.

## Import the complete source

Use the prepared `Alpha_Labs_v0.6_Full_Repository.zip` package from the ChatGPT conversation. Extract its inner `alpha-labs/` directory and upload its contents into this repository (do not upload the ZIP itself as the only file). Keep `.github/`, `apps/`, `packages/`, `contracts/`, `tests/`, `docs/`, `pyproject.toml`, `scripts/`, and `.gitignore`. Exclude `__pycache__`, `*.pyc`, `.env` credentials and generated data. The source ZIP is not accessible to GitHub until imported.

Once imported, from the repository root run:

```sh
python -m pip install -e .
python -m unittest discover -s tests/unit -p 'test_research_foundation.py' -v
cd apps/sites && node --test tests/*.test.cjs
```

Research uses synthetic data initially; no brokerage account or wallet credentials should be committed.
