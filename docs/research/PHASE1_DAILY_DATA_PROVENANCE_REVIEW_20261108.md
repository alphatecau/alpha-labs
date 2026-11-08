# Phase 1 daily market-data gates — review record (2026-11-08)

**PR:** #19 (draft) · **Reviewed source SHA:** `7198ceea9a4716f34f76561999d547d99988f566` · **Decision:** ACCEPT FOR RESEARCH-ONLY REVIEW; **NOT CERTIFIED DATA PROVENANCE**.

## Verified GitHub evidence
- GitHub reported the draft PR mergeable against main `36d486fe590985d7c1ab30eee83bdf6db9e1bcaf`.
- Research workflow run [42480875989](https://github.com/alphatecau/alpha-labs/actions/runs/42480875989) completed successfully.
- Sites workflow run [42480875962](https://github.com/alphatecau/alpha-labs/actions/runs/42480875962) completed successfully.
- Source inspection confirms UTC hourly continuity, OHLCV validation, checksum equality, calendar-session equality and corporate-action *declaration* checks.
- These observations do not constitute an independent third-party review of input-data authenticity.

## Threat model and limitations
1. **Checksum is an integrity check, not authentication.** An attacker or faulty ingestion job that supplies both CSV and its checksum can make altered data pass.
2. **Calendar is caller-supplied.** Completeness against an incorrect or incomplete session calendar does not establish genuine exchange-calendar completeness.
3. **Corporate-action flag is self-declared.** A CSV value of `true` cannot prove that dividends, splits or other adjustments are accurate.
4. **Adjusted-close-only ETF input is insufficient for execution simulation.** It cannot establish realistic intraday fill prices, opening gaps, bid-ask spreads, short borrow or total-return treatment.
5. **UTC aggregation does not authenticate exchange provenance.** Correct 24-hour spacing and valid OHLCV bounds do not establish that bars are genuine or free of venue outages.
6. **Research-only restriction:** no profitable/validated strategy claims, live execution, broker integration or deployment are authorised by this PR.

## Follow-up acceptance gates
- [ ] Attach independently sourced, timestamped, immutable data manifest with publisher, download time, symbol mapping, timezone and hash.
- [ ] Verify ETF sessions against an independently sourced exchange calendar and document early closes/holidays.
- [ ] Validate splits/dividends and adjusted prices against independent corporate-action records.
- [ ] Add explicit point-in-time publication lag and survivorship/delistings fixtures before equity/ETF strategy promotion.
- [ ] Review invalid field types, overflow, malformed timestamps and source mismatch in adversarial tests.
- [ ] Re-run CI on the final reviewed head and record run IDs.
- [ ] Obtain independent code/data review before production use.

**Disposition:** keep PR #19 draft pending the above research-data provenance work or a documented scope-limited approval. Keep PR #17 draft; live trading disabled.
