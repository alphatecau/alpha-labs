"""Offline adversarial checks for session and PIT gates."""
import unittest
from datetime import date, datetime, timedelta, timezone
from dataclasses import replace

from alpha_lab.data.session_pit import SessionCalendar, PointInTimeRecord, validate_daily_sessions
from alpha_lab.data.provider_neutral import CanonicalOHLCV, ResearchDataset
from decimal import Decimal

UTC = timezone.utc


class SessionPitTests(unittest.TestCase):
    def setUp(self):
        dates = (date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6))
        self.calendar = SessionCalendar.from_explicit_dates(
            venue="TESTX", session_dates=dates, calendar_source="unverified-test-calendar")
        bars = tuple(CanonicalOHLCV(datetime.combine(d, datetime.min.time(), UTC),
                                   Decimal(100), Decimal(105), Decimal(99),
                                   Decimal(102), Decimal(10)) for d in dates)
        self.dataset = ResearchDataset(bars, {"interval_minutes": 1440,
            "venue": "TESTX", "csv_sha256": "a" * 64}, "b" * 64)

    def test_explicit_sessions_skip_weekend(self):
        validate_daily_sessions(self.dataset, self.calendar)
        self.assertEqual(len(self.calendar.calendar_sha256), 64)

    def test_missing_extra_and_duplicate_sessions(self):
        for bars in (self.dataset.bars[:-1], self.dataset.bars + (self.dataset.bars[-1],),
                     self.dataset.bars[:1] + self.dataset.bars[2:]):
            with self.subTest(length=len(bars)), self.assertRaises(ValueError):
                validate_daily_sessions(replace(self.dataset, bars=bars), self.calendar)

    def test_calendar_rejects_unsorted_and_duplicates(self):
        for dates in ((date(2025, 1, 3), date(2025, 1, 2)),
                      (date(2025, 1, 2), date(2025, 1, 2))):
            with self.assertRaises(ValueError):
                SessionCalendar.from_explicit_dates(
                    venue="TESTX", session_dates=dates, calendar_source="fixture")

    def test_pit_accepts_known_temporal_order_only(self):
        record = PointInTimeRecord("a" * 64,
            datetime(2025, 1, 7, tzinfo=UTC),
            datetime(2025, 1, 7, 1, tzinfo=UTC),
            datetime(2025, 1, 7, 2, tzinfo=UTC))
        record.validate(self.dataset)
        with self.assertRaises(ValueError):
            replace(record, decision_at_utc=datetime(2025, 1, 6, tzinfo=UTC)).validate(self.dataset)
        with self.assertRaises(ValueError):
            replace(record, source_sha256="0" * 64).validate(self.dataset)
        with self.assertRaises(ValueError):
            replace(record, commercial_rights_verified=True).validate(self.dataset)

    def test_pit_rejects_naive_timestamps(self):
        record = PointInTimeRecord("a" * 64, datetime(2025, 1, 7),
            datetime(2025, 1, 7, 1, tzinfo=UTC),
            datetime(2025, 1, 7, 2, tzinfo=UTC))
        with self.assertRaises(ValueError):
            record.validate(self.dataset)


if __name__ == "__main__":
    unittest.main()
