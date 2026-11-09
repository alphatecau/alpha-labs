# Alpha Labs — Provider-neutral offline research foundation

## Audit
Existing `data/csv_import.py` already validates strict UTC timestamps, 80+ candles, contiguous intervals, Decimal OHLCV, quote currency, and raw SHA-256. `data/manifests.py` already produces and verifies fail-closed provenance manifests. `examples/generate_synthetic_candles.py` already generates deterministic offline synthetic fixtures. `data/adapters/binance_archive.py` remains a separate provider-specific research path with licensing constraints.

## Changes
`data/provider_neutral.py` provides a canonical immutable UTC OHLCV model and a provider-independent offline load/verify boundary. It reuses existing validators rather than weakening or duplicating them. It requires explicit source classification, symbol, venue, retrieval timestamp and quote currency. Raw and metadata hashes prove integrity only; authenticity, commercial rights, point-in-time availability, independent price verification and profitability remain **unverified**. Trading remains disabled.

## Acceptance
Run `PYTHONPATH=packages/alpha_lab/src python -m unittest discover -s tests/unit -p 'test_*.py' -v`. Existing offline synthetic fixture and website tests must remain green. This change does not download data, call a provider, expose credentials, merge or deploy. A commercial provider requires a separately approved adapter and data licence.
