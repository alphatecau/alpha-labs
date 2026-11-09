"""No-network daily session ingestion and adversarial validation tests."""
import csv
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from alpha_lab.data.daily_session_import import load_daily_sessions, verify_daily_sessions
from alpha_lab.data.session_pit import SessionCalendar

UTC = timezone.utc


class DailySessionImportTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "daily.csv"
        # Deliberately explicit synthetic weekday sessions, not an authoritative calendar.
        dates = []
        d = date(2025, 1, 1)
        while len(dates) < 80:
            if d.weekday() < 5:
                dates.append(d)
            d += timedelta(days=1)
        self.calendar = SessionCalendar.from_explicit_dates(
            venue="TESTX", session_dates=dates, calendar_source="synthetic-calendar")
        self.rows = [[d.isoformat(), "100", "105", "99", "102", "1000"] for d in dates]
        self.capture = datetime(2025, 6, 1, tzinfo=UTC)
        self.write()

    def write(self):
        with self.path.open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["session_date", "open", "high", "low", "close", "volume"])
            writer.writerows(self.rows)

    def load(self, **changes):
        kwargs = dict(calendar=self.calendar,
            expected_calendar_sha256=self.calendar.calendar_sha256,
            instrument="TESTETF", quote_currency="USD",
            captured_at_utc=self.capture,
            available_at_utc=self.capture + timedelta(minutes=1),
            decision_at_utc=self.capture + timedelta(minutes=2))
        kwargs.update(changes)
        return load_daily_sessions(self.path, **kwargs)

    def test_weekend_gaps_are_valid_only_when_explicit(self):
        result = self.load()
        self.assertEqual(len(result.bars), 80)
        self.assertFalse(result.verified_prices)
        verify_daily_sessions(self.path, result, calendar=self.calendar,
            captured_at_utc=self.capture,
            available_at_utc=self.capture + timedelta(minutes=1),
            decision_at_utc=self.capture + timedelta(minutes=2))

    def test_calendar_fingerprint_is_required(self):
        with self.assertRaises(ValueError):
            self.load(expected_calendar_sha256="0" * 64)

    def test_missing_extra_duplicate_sessions_rejected(self):
        original = self.rows
        for rows in (original[:-1], original + [original[-1]],
                     original[:5] + original[6:]):
            self.rows = rows
            self.write()
            with self.assertRaises(ValueError):
                self.load()
        self.rows = original
        self.write()

    def test_invalid_ohlcv_and_modified_source_rejected(self):
        record = self.load()
        self.rows[2][4] = "NaN"
        self.write()
        with self.assertRaises(ValueError):
            self.load()
        self.rows[2][4] = "103"
        self.write()
        with self.assertRaises(ValueError):
            verify_daily_sessions(self.path, record, calendar=self.calendar,
                captured_at_utc=self.capture,
                available_at_utc=self.capture + timedelta(minutes=1),
                decision_at_utc=self.capture + timedelta(minutes=2))

    def test_future_availability_rejected(self):
        with self.assertRaises(ValueError):
            self.load(available_at_utc=self.capture + timedelta(hours=2),
                      decision_at_utc=self.capture + timedelta(hours=1))

    def test_claims_and_canonical_mutation_rejected(self):
        record = self.load()
        for changed in (replace(record, trading_enabled=True),
                        replace(record, bars=record.bars[:-1])):
            with self.assertRaises(ValueError):
                verify_daily_sessions(self.path, changed, calendar=self.calendar,
                    captured_at_utc=self.capture,
                    available_at_utc=self.capture + timedelta(minutes=1),
                    decision_at_utc=self.capture + timedelta(minutes=2))


if __name__ == "__main__":
    unittest.main()
