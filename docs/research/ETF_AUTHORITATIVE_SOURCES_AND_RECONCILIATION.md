# ETF authoritative source acquisition and reconciliation plan

**Status:** SOURCE IDENTIFICATION COMPLETE; DATASET INGESTION AND PRICE RECONCILIATION BLOCKED. Research-only. No live trading.

## Authoritative sources verified from public documentation
- **NYSE exchange calendar:** https://www.nyse.com/trade/hours-calendars ; official yearly calendar PDF https://www.nyse.com/publicdocs/nyse/ICE_NYSE_2026_Yearly_Trading_Calendar.pdf . Download an official date-specific schedule and preserve exact downloaded bytes and SHA-256. Check holidays, early closes and subsequent corrections.
- **NYSE corporate-action feed:** https://www.nyse.com/market-data/corporate-actions/market-event-feed . NYSE documents historical and real-time corporate-action API; access is a paid product. Verify the security/ETF and coverage before use.
- **Nasdaq Daily List:** https://www.nasdaq.com/products/data/equities/corporate-action-solutions . Nasdaq documents dividend, split and ex-date records, historical search and agreement/approval requirements. Nasdaq-listed coverage does not automatically cover every NYSE Arca ETF.
- **ETF issuer:** Obtain official fund distributions, splits and historical NAV/price-adjustment methodology for each specific ETF. The issuer's declaration is necessary for issuer-specific cross-checks; an exchange feed alone does not certify adjusted-close methodology.

## Required immutable input manifest per dataset
- Source legal entity and official HTTPS URL, product/version, market venue, instrument identifiers (ticker, exchange, stable security identifier), date range, UTC acquisition timestamp, timezone and licence/redistribution permissions.
- SHA-256 of raw downloaded bytes, response metadata and retrieval method; preserve original bytes read-only.
- Evidence publication timestamp and earliest permissible use time for each corporate action; fail closed when the source did not publish it by the backtest decision timestamp.
- Independent calendar and issuer/action records; reconcile symbol changes, delistings, holidays and early closes.
- Price adjustment convention: raw close, split-adjusted close or total-return adjusted close. Reconstruct adjustment factors from dated split and dividend records and compare with vendor adjusted close under declared rounding tolerance. Do not silently treat dividends as price-only split adjustments.

## Blocking acceptance tests
1. Obtain actual official calendar data and the legally accessible ETF-specific corporate-action and raw/adjusted price histories; no simulated files may be labelled authentic.
2. Independently check source identities, licence terms, point-in-time availability and completeness for the requested backtest window.
3. Add a deterministic replay fixture from real downloaded files with exact hashes and documented expected adjustment factors.
4. Test conflicting split ratios, missing dividends, restated records, late publication, delisted symbols, ticker reuse and inconsistent exchange sessions.
5. Confirm adjusted-price reconciliation against the issuer/vendor methodology, including cash dividend treatment; require independent review.

## Implementation boundary
The current `phase1_external_evidence.py` validates **caller-supplied** CSV records, hashes, timestamp ordering and cross-file consistency. It explicitly returns `publisher_identity_verified=False`, `adjusted_prices_independently_reconciled=False` and `eligible_for_strategy_promotion=False`. It is **not** a source connector and does not prove provenance. The example tests use synthetic files only.

**Decision:** No authentic ETF historical datasets or credentials were supplied in this task. External dataset acquisition and corporate-action adjusted-price reconciliation remain BLOCKED. Keep PR #19 in draft and trading disabled.
