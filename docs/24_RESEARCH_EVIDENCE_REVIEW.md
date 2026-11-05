# Multi-year research evidence review — 5 November 2026

Status: the subsequent complete upload passed independent engineering review. The EMA baseline failed the economic promotion screen. See [the completed audit](25_MULTYEAR_EVIDENCE_REVIEW_20261105.md) for current findings. Trading remains disabled.

## Initial review before the complete evidence upload

- PR #8 initially contained nine files at `bd10dacaa56949ff5f08d719aa73783f5c4f37e2`. Both PR workflows passed, and 93 Python plus 36 website tests passed independently before the additional changes below.
- Available Termux screenshots show completed reports for **April 2023–December 2025**, not January 2023–December 2025. The repeated SOL evaluation stops at the intentional no-overwrite guard. That exception does not mean the prior report failed.
- The last screenshot shows an archive containing three report JSONs and three frozen-specification JSONs. It does not include the curated CSVs, dataset manifests, monthly source archives or checksum files. Its bytes are not available in this review; screenshot numbers and a displayed hash do not establish reproducibility.
- The same provider's public Spot REST response currently omits **24 March 2023 13:00 UTC** between its 12:00 and 14:00 hourly observations. The 12:00 bar also has early close metadata. This corroborates a REST data gap, not the exact bytes of the cached monthly archive. No candle is filled or invented.
- For 24 January 2023 12:00 UTC, current REST returns the canonical 12:59:59.999 close timestamp. The previously reported monthly-archive anomaly at row 565 remains unverified. Current REST data cannot establish what a previously cached archive contained.

The exact public REST requests and observations are retained in [`evidence/2026-11-05_BINANCE_REST_SAMPLES.json`](evidence/2026-11-05_BINANCE_REST_SAMPLES.json). These are provider observations, not synthetic test fixtures or an independent venue price check.

## Source binding defect and fix

The previous verifier separately checked the curated CSV against its own manifest and the cached ZIPs against their checksum records. It did not reconstruct the CSV from those ZIPs. A different, structurally valid CSV with consistently recomputed local metadata could therefore pass while claiming the original archive provenance. Likewise, internally consistent metadata could relabel the source class.

Two regression cases reproduced both failures before the fix. Verification now enforces the Binance spot provenance fields and hashes the canonical CSV reconstructed from every checksum-verified source archive. That digest must match the curated CSV. This closes the local source-linkage gap; the provider's checksum is still not an independent authentication of market prices or a cryptographic seal against coordinated replacement of every source and record.

Existing correctly assembled datasets/specifications remain valid. No data, experiment or report is rewritten by verification.

## Complete evidence export on Termux

After updating the existing development checkout, run:

```sh
cd ~/alpha-labs-multiyear
git pull --ff-only
PYTHONPATH=packages/alpha_lab/src python scripts/export_research_evidence.py --from-month 2023-04 --through-month 2025-12 --output ~/storage/downloads/AlphaLabs_Research_Evidence_COMPLETE_20261105.tar.gz
```

The exporter is standard-library only and makes no network request. It verifies source linkage, checks the frozen specs, reruns each stored report using the production minimum-history requirement, and compares all result fields. Hashes, labels and counts must match exactly; floating-point metrics allow only rounding-level tolerance (`1e-12` relative/absolute).

The new bundle contains the selected CSVs, manifests, original ZIP/checksum pairs, specifications, reports and Python research source, with a per-file byte count and SHA-256 inventory. It also includes cached BTC January/March 2023 archives when available. Rejected forensic archives retain explicit structural errors; missing forensic samples are labelled unavailable. It refuses to overwrite an existing bundle and does not alter the original evidence.

Upload the resulting `AlphaLabs_Research_Evidence_COMPLETE_20261105.tar.gz` for independent inspection. The phone's Downloads directory is outside this review environment, so its files cannot be retrieved automatically.

## Evidence gate and outcome

The complete `AlphaLabs_Evidence.zip` upload contained the expected inner archive, all source datasets and original archives. Its inventory, source linkage, real anomaly rows and all three reports have now been inspected and reproduced. The earlier January attribution is corrected by the actual March archive record in the completed audit. The April start remains a selection made after inspecting data quality; it does not restore holdout independence.

The engineering evidence gate is complete for the reviewed infrastructure. Preserve EMA(12,48) as a frozen comparator and reject it for promotion: all three unsealed test returns are negative and below allocation-matched passive hold. Strategy Research v0.8 still requires its own registered hypothesis and future evidence. No paper/live execution, broker integration or profitability approval is introduced.

Provider documentation: [Binance public-data format, checksums and correction policy](https://github.com/binance/binance-public-data). The provider documents microsecond Spot timestamps from 1 January 2025 and notes that archives can later be corrected. A current REST response or download must not be assumed identical to the original cached source.
