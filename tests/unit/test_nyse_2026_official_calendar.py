"""NYSE 2026 published schedule regression cases.

Reference: https://www.nyse.com/trade/hours-calendars
These are source-grounded static fixtures, not a continuously updated venue calendar.
"""
import unittest
from datetime import datetime, timezone
from alpha_lab.research.phase3_integrity import Session, next_eligible_open, require_settlement_at_open

def instant(month,day,hour,minute=0):
    return datetime(2026,month,day,hour,minute,tzinfo=timezone.utc)

class NYSE2026PublishedCalendarTests(unittest.TestCase):
    def test_good_friday_2026_closed_and_monday_reopens(self):
        sessions=[
            Session(instant(4,2,13,30),instant(4,2,20)),
            Session(instant(4,6,13,30),instant(4,6,20)),
        ]
        self.assertEqual(next_eligible_open(instant(4,2,19),sessions),instant(4,6,13,30))
        with self.assertRaises(ValueError):
            require_settlement_at_open(instant(4,2,19),instant(4,3,13,30),sessions)

    def test_day_after_thanksgiving_early_close(self):
        sessions=[
            Session(instant(11,25,14,30),instant(11,25,21)),
            Session(instant(11,27,14,30),instant(11,27,18)),
            Session(instant(11,30,14,30),instant(11,30,21)),
        ]
        self.assertEqual(next_eligible_open(instant(11,25,20),sessions),instant(11,27,14,30))
        self.assertEqual(next_eligible_open(instant(11,27,17),sessions),instant(11,30,14,30))

if __name__ == "__main__":
    unittest.main()
