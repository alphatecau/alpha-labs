# Session-aware and point-in-time offline validation

This research-only module accepts **explicit** exchange-session dates rather than treating weekends as missing daily candles. Calendar dates and their SHA-256 fingerprint are reproducible but **not independently authenticated**. The calendar must be supplied and checked against a separately licensed authoritative venue calendar before use with real equities/ETFs.

The `PointInTimeRecord` checks source-byte SHA-256 and UTC chronology: capture <= availability <= decision, with no observations after capture. These fields are supplied assertions, **not independent evidence of actual publication, ingestion or as-of availability**. A future trustworthy capture service must supply signed/tamper-evident timestamps and archive source revisions; this module alone does not establish PIT integrity.

The existing strict hourly CSV loader remains unchanged. Daily session-aware validation is a separate boundary because its exact-contiguous-hours requirement is inappropriate for US equities across weekends and holidays. This module does not ingest real data, validate trading calendars from an exchange, verify commercial rights, adjust corporate actions, or authorise trading.

Run `PYTHONPATH=packages/alpha_lab/src python -m unittest discover -s tests/unit -p 'test_*.py'`. No network, keys, provider subscription, merge or deployment.
