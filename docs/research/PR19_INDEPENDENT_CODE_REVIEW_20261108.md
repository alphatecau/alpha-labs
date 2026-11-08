# PR #19 independent code review — 2026-11-08

**Reviewed head:** `295eafbff66090fd43b8922d08e6186b09732614`  
**Decision:** **CONDITIONAL / DO NOT PROMOTE.** Automated CI passes; source provenance and production suitability remain unverified. This is a model-assisted source review, not independent human sign-off.

## Evidence
- Offline research tests: https://github.com/alphatecau/alpha-labs/actions/runs/42481421285 — success.
- Sites tests: https://github.com/alphatecau/alpha-labs/actions/runs/42481421320 — success.
- GitHub reports PR mergeable, draft and unmerged.
- Reviewed four research modules and their stated validation boundaries.

## Confirmed safeguards
- 24-hour UTC crypto aggregation rejects incomplete days, intra-day missing hours and whole missing days between consecutive candles.
- ETF CSV checks supplied SHA-256, symbol, adjusted-close numeric bounds and equality to a caller-supplied session calendar.
- External evidence checks independently supplied calendar and action CSVs for consistency and pinned hashes.
- Point-in-time module checks supplied publication/retrieval timestamps against decision time.
- Split reconciliation compares supplied raw closes to split-adjusted closes and rejects dividend-bearing inputs.

## Open findings (not resolved by green CI)
**P1 — Historical point-in-time semantics:** `phase1_pit_availability.verify_evidence_available` rejects evidence physically retrieved after a historical decision. This is conservative, but makes ordinary retrospective research impossible without archival evidence of contemporaneous availability. A documented archival-publication proof and separate research-download timestamp model are needed. Never bypass this by backdating retrieval times.

**P1 — Corporate-action completeness:** `phase1_external_evidence` requires an action record on every session but cannot prove that the provider actually included all splits and distributions. Caller-provided publisher labels and hashes do not authenticate publisher identity or original bytes.

**P1 — Dividend-adjusted returns unsupported:** `phase1_split_reconciliation` deliberately rejects cash dividends. This is appropriate for fail-closed behaviour, but does not support real ETF total-return validation.

**P2 — ETF CSV error handling:** malformed dates or empty date fields can raise raw `ValueError`/`TypeError` rather than consistent domain-specific validation errors. Rejects data, but error diagnostics should be standardised.

**P2 — Calendar evidence scope:** a caller-supplied session set may omit the intended backtest interval entirely; no explicit start/end coverage or independent official holiday verification is enforced.

**P2 — Crypto source authenticity:** hourly spacing, OHLC bounds and finite values do not validate exchange source, missing trade events, stale quotes or venue-specific market outages.

## Required next gates
1. Obtain actual, licence-compliant, publisher-authenticated raw/adjusted ETF prices, official exchange calendar and issuer/exchange corporate-action evidence, with immutable source manifests.
2. Implement archival point-in-time availability without falsifying acquisition timestamps; prove historical publication availability independently.
3. Define a dividend/total-return adjustment convention, reconcile against independent issuer records and test restatements.
4. Add explicit interval coverage, adversarial source-manifest tests and consistent malformed-input errors.
5. Obtain separate human reviewer approval and rerun CI on final commit before any merge decision.

**Release restrictions:** research-only; PR #19 remains draft; no merge, broker integration, deployment or live trading.
