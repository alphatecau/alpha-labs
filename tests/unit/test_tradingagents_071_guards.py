import hashlib
import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from alpha_lab.research.point_in_time_guards import (
    calendar_date, require_available, require_final_candle,
    finite_decimal, reconcile_nav, validate_manifest,
)

UTC = timezone.utc
def at(y,m,d,h=0):
    return datetime(y,m,d,h,tzinfo=UTC)

class TradingAgents071GuardTests(unittest.TestCase):
    def test_unpadded_date_is_chronological(self):
        self.assertLess(calendar_date("2024-7-5"), calendar_date("2024-07-06"))
        with self.assertRaises(ValueError): calendar_date("2024-13-1")

    def test_future_filing_rejected(self):
        with self.assertRaisesRegex(ValueError, "future publication"):
            require_available(at(2024,7,6), at(2024,7,5))
        require_available(at(2024,7,5), at(2024,7,5))

    def test_unknown_timestamp_fails_closed(self):
        with self.assertRaises(ValueError): require_available(None, at(2024,7,5))
        with self.assertRaises(ValueError): require_available(datetime(2024,7,5), at(2024,7,5))

    def test_partial_candle_rejected_and_final_accepted(self):
        with self.assertRaisesRegex(ValueError, "unfinished"):
            require_final_candle(at(2026,1,1,10), 60, at(2026,1,1,10))
        require_final_candle(at(2026,1,1,10), 60, at(2026,1,1,11))

    def test_nonfinite_values_rejected(self):
        for v in ["NaN", "Infinity", "-Infinity", True]:
            with self.subTest(v=v), self.assertRaises(ValueError): finite_decimal(v)

    def test_small_prices_preserve_decimal_precision(self):
        self.assertEqual(reconcile_nav("1", {"BTCUSDT": "100"}, {"BTCUSDT": "0.00000123"}), Decimal("1.00012300"))

    def test_symbol_mismatch_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "instrument/mark mismatch"):
            reconcile_nav("10", {"BTCUSDT": "1"}, {"BTC/USDT": "100"})

    def test_bad_portfolio_rejected(self):
        with self.assertRaises(ValueError): reconcile_nav("NaN", {}, {})
        with self.assertRaises(ValueError): reconcile_nav("10", {"BTC": "-1"}, {"BTC": "100"})

    def test_manifest_integrity_and_provenance(self):
        payload=b"synthetic fixtures only"
        sha=hashlib.sha256(payload).hexdigest()
        self.assertEqual(validate_manifest(payload,sha,"synthetic-fixture"),sha)
        with self.assertRaisesRegex(ValueError, "checksum"):
            validate_manifest(payload+b"!",sha,"synthetic-fixture")
        with self.assertRaisesRegex(ValueError, "provenance"):
            validate_manifest(payload,sha,"unknown")
if __name__ == "__main__":
    unittest.main()
