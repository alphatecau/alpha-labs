import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from alpha_lab.data.csv_import import Bar
from alpha_lab.research.breakout_candidate import breakout_signals

def fixture(hours=1200):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return tuple(
        Bar(start + timedelta(hours=i), Decimal(100)+Decimal(i)/10,
            Decimal(101)+Decimal(i)/10, Decimal(99)+Decimal(i)/10,
            Decimal(100)+Decimal(i)/10, Decimal(10))
        for i in range(hours)
    )

class BreakoutCandidateTests(unittest.TestCase):
    def test_deterministic_and_no_signal_before_warmup(self):
        bars = fixture()
        first = breakout_signals(bars)
        self.assertEqual(first, breakout_signals(bars))
        self.assertEqual(len(first), len(bars))
        self.assertFalse(any(first[:840]))

    def test_future_changes_cannot_modify_past_signals(self):
        bars = fixture()
        earlier = breakout_signals(bars[:1100])
        later = breakout_signals(bars)
        self.assertEqual(earlier, later[:1100])

    def test_gap_fails_closed(self):
        bars = fixture()
        with self.assertRaisesRegex(ValueError, "Missing"):
            breakout_signals(bars[:500]+bars[501:])

    def test_rejects_parameter_search(self):
        with self.assertRaisesRegex(ValueError, "Frozen"):
            breakout_signals(fixture(), breakout_lookback=15)

    def test_empty_input(self):
        self.assertEqual(breakout_signals(()), [])

if __name__ == "__main__":
    unittest.main()
