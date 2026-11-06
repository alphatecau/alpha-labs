import unittest
from datetime import date, time, timedelta
from types import SimpleNamespace

from alpha_lab.domain.assets import AssetClass, Instrument
from alpha_lab.data.equity_sessions import (
    USSession, verify_equity_bars
)

EQUITY = Instrument(
    "AAPL", AssetClass.US_EQUITY, "XNAS", "USD", "XNAS"
)


def bars(session):
    step = timedelta(minutes=30)
    count = int((session.closes_utc - session.opens_utc) / step)
    return [
        SimpleNamespace(time=session.opens_utc + i * step)
        for i in range(count)
    ]


class SessionTests(unittest.TestCase):

    def test_daylight_saving(self):
        march = USSession.from_et("XNAS", date(2026, 3, 9))
        november = USSession.from_et("XNAS", date(2026, 11, 2))
        self.assertEqual(march.opens_utc.hour, 13)
        self.assertEqual(november.opens_utc.hour, 14)

    def test_regular_session(self):
        s = USSession.from_et("XNAS", date(2026, 11, 2))
        self.assertEqual(verify_equity_bars(EQUITY, [s], bars(s)), 13)

    def test_early_close(self):
        s = USSession.from_et(
            "XNAS", date(2026, 11, 27), time(13)
        )
        self.assertEqual(verify_equity_bars(EQUITY, [s], bars(s)), 7)

    def test_missing_candle(self):
        s = USSession.from_et("XNAS", date(2026, 11, 2))
        with self.assertRaises(ValueError):
            verify_equity_bars(EQUITY, [s], bars(s)[:-1])

    def test_holiday_gap_with_supplied_schedule(self):
        a = USSession.from_et("XNAS", date(2026, 11, 25))
        b = USSession.from_et(
            "XNAS", date(2026, 11, 27), time(13)
        )
        self.assertEqual(
            verify_equity_bars(
                EQUITY, [a, b], bars(a) + bars(b)
            ), 20
        )

    def test_weekend_rejected(self):
        with self.assertRaises(ValueError):
            USSession.from_et("XNAS", date(2026, 11, 7))

    def test_hourly_interval_rejected(self):
        s = USSession.from_et("XNAS", date(2026, 11, 2))
        with self.assertRaises(ValueError):
            verify_equity_bars(EQUITY, [s], bars(s), minutes=60)


if __name__ == "__main__":
    unittest.main()
