"""Offline adversarial market-session fixtures: no external calendar authority implied."""
import unittest
from datetime import datetime, timezone, timedelta
from alpha_lab.research.phase3_integrity import Session, next_eligible_open, require_settlement_at_open

def utc(y,m,d,h=0,minute=0):
    return datetime(y,m,d,h,minute,tzinfo=timezone.utc)

class ExchangeSessionAdversarialTests(unittest.TestCase):
    def test_weekend_and_holiday_closure(self):
        sessions=(Session(utc(2026,4,2,13),utc(2026,4,2,20)),
                  Session(utc(2026,4,7,13),utc(2026,4,7,20)))
        self.assertEqual(next_eligible_open(utc(2026,4,2,19),sessions),utc(2026,4,7,13))
        with self.assertRaises(ValueError):
            require_settlement_at_open(utc(2026,4,2,19),utc(2026,4,3,13),sessions)

    def test_dst_session_utc_offset_explicit(self):
        # No timezone inference: UTC sessions supplied by trusted calendar adapter.
        sessions=(Session(utc(2026,3,6,14,30),utc(2026,3,6,21)),
                  Session(utc(2026,3,9,13,30),utc(2026,3,9,20)))
        self.assertEqual(next_eligible_open(utc(2026,3,6,20),sessions),utc(2026,3,9,13,30))

    def test_unknown_or_malformed_calendar_rejected(self):
        with self.assertRaises(ValueError):
            next_eligible_open(utc(2026,3,6),())
        with self.assertRaises(ValueError):
            next_eligible_open(utc(2026,3,6),[Session(utc(2026,3,9,20),utc(2026,3,9,13))])

    def test_no_same_open_execution(self):
        sessions=[Session(utc(2026,3,9,13,30),utc(2026,3,9,20)),
                  Session(utc(2026,3,10,13,30),utc(2026,3,10,20))]
        self.assertEqual(next_eligible_open(utc(2026,3,9,13,30),sessions),utc(2026,3,10,13,30))
