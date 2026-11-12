# Phase 3 — research integrity verification

Research branch only; no production migration, credentials, live database connection or trading.

## Implemented
- PostgreSQL DDL with `PRIMARY KEY (owner_id, run_id)`; INSERT without conflict suppression, so duplicate keys fail at database level when the schema is applied.
- Parameterised insert adapter with caller-owned transaction. No DB driver or live connection is required for offline research.
- Explicit UTC exchange session intervals with strict next-opening settlement eligibility and rejection of missing/overlapping schedules.
- Independent long-only cash, position, realised/unrealised liquidation P&L, fees and NAV reconciliation for existing offline replay order format.
- Deterministic adversarial tests for duplicate identifiers, invalid evidence, missing sessions, holiday gaps, overlapping sessions and NAV tampering.

## Limitations / blockers
- PostgreSQL migration NOT applied; concurrency, transaction rollback and restart persistence NOT verified against a real PostgreSQL instance.
- Session fixtures are synthetic, not an authoritative licensed exchange calendar. Crypto 24/7 and equities require different validated calendars and venue halt metadata.
- Session-aware settlement guard is not automatically applied to every replay call. Existing OHLCV replay uses next available bar; calendar guard must be wired at venue-aware ingestion/settlement boundary.
- Independent reconciliation is a verifier for existing long-only offline order format, not a short/multi-asset/derivatives ledger.
- CI must be checked on the final commit before any merge.
