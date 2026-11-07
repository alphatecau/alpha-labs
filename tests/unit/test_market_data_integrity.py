import unittest
from tools.market_data_integrity import (
    MarketDataError, validate_quote, conservative_fill_cost_bps,
)


def quote():
    return {
        "venue": "synthetic-venue", "instrument": "TEST/USD",
        "source_id": "fixture-1",
        "event_time": "2026-11-07T00:00:00.000Z",
        "received_time": "2026-11-07T00:00:00.100Z",
        "decision_time": "2026-11-07T00:00:01.000Z",
        "bid": "99.9", "ask": "100.1",
        "bid_size": "2", "ask_size": "3",
    }


class MarketDataIntegrityTests(unittest.TestCase):
    def test_valid_quote(self):
        self.assertGreater(float(validate_quote(quote())["spread_bps"]), 0)

    def test_future_event_rejected(self):
        data = quote()
        data["event_time"] = "2026-11-07T00:00:02.000Z"
        with self.assertRaises(MarketDataError):
            validate_quote(data)

    def test_stale_rejected(self):
        with self.assertRaises(MarketDataError):
            validate_quote(quote(), max_staleness_ms=500)

    def test_crossed_rejected(self):
        data = quote()
        data["bid"] = "101"
        with self.assertRaises(MarketDataError):
            validate_quote(data)

    def test_nan_rejected(self):
        data = quote()
        data["ask"] = "NaN"
        with self.assertRaises(MarketDataError):
            validate_quote(data)

    def test_missing_source_rejected(self):
        data = quote()
        data["source_id"] = ""
        with self.assertRaises(MarketDataError):
            validate_quote(data)

    def test_cost_is_positive(self):
        checked = validate_quote(quote())
        self.assertGreater(conservative_fill_cost_bps(
            checked, side="BUY", quantity="1", fee_bps="10"), 10)

    def test_insufficient_depth_rejected(self):
        checked = validate_quote(quote())
        with self.assertRaises(MarketDataError):
            conservative_fill_cost_bps(
                checked, side="BUY", quantity="4", fee_bps="10")

    def test_negative_fee_rejected(self):
        checked = validate_quote(quote())
        with self.assertRaises(MarketDataError):
            conservative_fill_cost_bps(
                checked, side="SELL", quantity="1", fee_bps="-1")

    def test_timezone_rejected(self):
        data = quote()
        data["event_time"] = "2026-11-07T10:00:00+10:00"
        with self.assertRaises(MarketDataError):
            validate_quote(data)


if __name__ == "__main__":
    unittest.main()
