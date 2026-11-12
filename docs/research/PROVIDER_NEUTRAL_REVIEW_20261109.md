# Provider-neutral foundation independent review — 2026-11-09

## Scope and results
The existing `csv_import.load_csv` enforces 80+ complete OHLCV candles, positive finite prices, nonnegative finite volume, UTC-normalised timestamps, strictly increasing complete intervals, quote currency and source-byte SHA-256. `manifests.build_manifest` and `verify_manifest` enforce canonical metadata and reject claims of authenticated prices, independent verification or trading approval. The new `provider_neutral.load_offline_dataset` reuses these checks and maps to immutable canonical OHLCV values. No external provider or broker is called.

CI on initial PR head `b14024a63f88df8e4e1eb7c110a539ea0a399aeb`: offline research workflow 42550533656 SUCCESS, website workflow 42550533782 SUCCESS. Subsequent adversarial test commit requires its own CI result.

## Adversarial review
Additional tests reject tampered manifest identifiers and source class, inflated authentication/trading claims, and altered canonical observations. Existing tests cover invalid OHLCV, duplicate/irregular timestamps, retrieval predating the last candle close, and source file mutation.

## Material limitations
- File hashes and manifest metadata are integrity checks, **not** source authentication or proof of historical point-in-time availability.
- A source identifier, venue, instrument or `retrieved_at_utc` is user-provided metadata; the code cannot attest to its truth.
- `ResearchDataset.manifest` is a mutable dictionary despite the frozen outer dataclass. Consumers must use `verify_offline_dataset` before trusting stored data; future improvement: immutable or canonical serialised manifest.
- The CSV loader requires exact contiguous intervals and >=80 observations. This is suitable for continuous synthetic/crypto fixtures, **not** unmodified exchange-session daily equity bars across weekends and holidays.
- No corporate actions, adjusted-price semantics, symbol mapping, as-of revisions, external price reconciliation, licensing verification or production storage guarantees.
- No strategy profitability, executable fills or permission to trade can be inferred.

## Decision
Keep draft PR unmerged until latest CI passes and an independent reviewer confirms scope. Next work: session-aware calendars for equities, point-in-time snapshots and explicit commercial data rights, each on separate research branches. No deployment or trading.
