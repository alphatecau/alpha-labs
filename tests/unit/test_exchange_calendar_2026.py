import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from alpha_lab.domain.assets import AssetClass, Instrument
from alpha_lab.data.exchange_calendar_2026 import (
    sessions_2026, verify_official_2026_bars
)

AAPL = Instrument(
    "AAPL", AssetClass.US_EQUITY, "XNAS", "USD", "XNAS"
)


class OfficialCalendarTests(unittest.TestCase):

    def test_published_holidays(self):
        for day in (date(2026, 4, 3),
                    date(2026, 7, 3),
                    date(2026, 11, 26)):
            self.assertEqual(sessions_2026("XNYS", day, day), ())
            self.assertEqual(sessions_2026("XNAS", day, day), ())

    def test_published_early_closes(self):
        for day in (date(2026, 11, 27),
                    date(2026, 12, 24)):
            s = sessions_2026("XNAS", day, day)[0]
            self.assertEqual(
                s.closes_utc.astimezone(
                    ZoneInfo("America/New_York")
                ).hour, 13
            )

    def test_daylight_saving(self):
        march = sessions_2026(
            "XNAS", date(2026, 3, 9), date(2026, 3, 9)
        )[0]
        november = sessions_2026(
            "XNAS", date(2026, 11, 2), date(2026, 11, 2)
        )[0]
        self.assertEqual(march.opens_utc.hour, 13)
        self.assertEqual(november.opens_utc.hour, 14)

    def test_holiday_gap_and_validation(self):
        start = date(2026, 11, 25)
        end = date(2026, 11, 27)
        sessions = sessions_2026("XNAS", start, end)
        bars = []
        for s in sessions:
            step = timedelta(minutes=30)
            count = int((s.closes_utc - s.opens_utc) / step)
            bars.extend(
                SimpleNamespace(time=s.opens_utc + i * step)
                for i in range(count)
            )
        self.assertEqual(
            verify_official_2026_bars(AAPL, start, end, bars),
            20
        )
        with self.assertRaises(ValueError):
            verify_official_2026_bars(
                AAPL, start, end, bars[:-1]
            )

    def test_unsupported_year(self):
        with self.assertRaises(ValueError):
            sessions_2026(
                "XNYS", date(2027, 1, 1), date(2027, 1, 4)
            )


if __name__ == "__main__":
    unittest.main()
