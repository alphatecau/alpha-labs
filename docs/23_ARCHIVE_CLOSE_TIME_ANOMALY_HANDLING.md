# Alpha Labs: Binance archive close-time anomaly handling

Status: research-only ingestion repair, **not** profitability verification. Live, paper, margin and short execution remain disabled.

## Problem

The previous Binance monthly 1h archive parser rejected a row whenever `close_time` did not equal `open_time + 3,600 seconds - one source timestamp unit`. Exchange-published and SHA-256-valid historical data may contain an earlier `close_time` within the matching candle interval. These rows require explicit provenance and human review; they are not automatically evidence of locally corrupted downloads.

Independent inspection of the uploaded originals corrected the initial January attribution: **January 2023 has 744 complete hourly BTC candles and no early-close anomaly**. The actual early-close record is **March 2023 row 565**, opening 24 March at 12:00 UTC. Its close timestamp is `1679661581646`, versus canonical `1679662799999`; the 13:00 UTC candle is then missing. The March archive has 743 rows and remains rejected. See the [reproduction audit](25_MULTYEAR_EVIDENCE_REVIEW_20261105.md).

## Fixed contract

- SHA-256 checksums remain mandatory and must match the **official archive**.
- The SPOT timestamp unit is still milliseconds before January 2025 and microseconds from January 2025. Mixed units and out-of-interval close timestamps are rejected with their observed and expected values.
- **Open times must exactly match the complete hourly UTC grid**. Missing, duplicate, reordered or outside-month candles remain rejected, with explicit expected and observed timestamps.
- A `close_time` earlier than the canonical hour end, but **within the same hourly interval**, is accepted only when the caller provides an anomaly ledger. The open timestamp and source OHLCV values are never adjusted.
- Each anomaly is recorded with its input row, UTC open timestamp, original close timestamp, expected close timestamp, time unit, discrepancy and an independent-review flag. Manifests aggregate all anomalies and re-verify every recorded anomaly against the cached, checksum-verified source archive.
- A source archive is saved after its checksum passes, even if later structural validation fails. The cache is **not** a research-ready dataset: `build_dataset` still refuses to output a curated CSV on gaps or invalid rows.
- Experiments carry `source_close_timestamp_anomaly_count` and a `source_close_timestamp_anomalies_require_review` warning, and are never promoted to verified alpha.

## Known remaining limitation

The received BTC March 2023 archive and a separate provider REST query both omit 24 March 13:00 UTC. This patch **does not fabricate missing observations**, override the continuous-time requirement or allow the full 2023-01 through 2025-12 BTC range to pass. Stop at that gap and perform independent cross-source reconciliation or choose a separate explicitly defined uninterrupted evaluation window. The reproduced research explicitly uses April 2023–December 2025; selecting this window after inspection does not create an independent holdout.

## Safe staged validation on Termux

Run the original monthly command in an isolated development branch, without modifying the already merged `main`:

```sh
cd ~/alpha-labs-multiyear
export PYTHONPATH=packages/alpha_lab/src
python -m unittest discover -s tests/unit -p 'test_*.py' -q
python scripts/multi_year_research.py fetch --symbols BTCUSDT --from-month 2023-01 --through-month 2023-01
```

If January succeeds, inspect the metadata ledger:

```sh
python - <<'PY'
import json
from pathlib import Path
p=Path('datasets/curated/binance-vision/BTCUSDT-1h-2023-01_to_2023-01.manifest.json')
d=json.loads(p.read_text())
print('Anomaly count:', d['source_close_timestamp_anomaly_count'])
for record in d['source_archives'][0]['close_timestamp_anomalies'][:20]:
    print(record)
PY
```

If errors remain, they now contain observed and expected timestamps. Do not continue to `freeze` and `evaluate` until the relevant curated dataset, source archive manifest and spec exist and pass verification.

## Verification boundary

Synthetic fixture tests reproduce early-close metadata on row 565, check the 2025 microsecond change and reject timestamps outside the interval, missing candles and manifest tampering. Separate inspection of the actual cached archives now confirms the complete January month and the March early-close/missing-hour defect described above. These checks do not establish strategy profitability or independently authenticated market prices.
