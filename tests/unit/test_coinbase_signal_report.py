"""Research-only signal report never authorises execution."""
import unittest
from datetime import datetime, timedelta, timezone

from alpha_lab.research.coinbase_signal_report import research_report

NOW = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)


def snapshot():
    end = NOW
    return {
        "schema_version": 1,
        "provider": "AlphaLabs Coinbase read-only",
        "product_id": "BTC-USD",
        "product_type": "SPOT",
        "quote_currency": "USD",
        "granularity": "4h",
        "collected_at": NOW.isoformat().replace("+00:00", "Z"),
        "candles": [
            {
                "start": (end - timedelta(hours=4 * (60 - i))).isoformat().replace("+00:00", "Z"),
                "open": str(100 + i),
                "high": str(102 + i),
                "low": str(99 + i),
                "close": str(101 + i),
                "volume": "5",
                "complete": True,
            }
            for i in range(60)
        ],
    }


class CoinbaseSignalReportTests(unittest.TestCase):
    def test_uptrend_is_not_a_trade_instruction(self):
        result = research_report(snapshot(), now=NOW)
        self.assertEqual(result["trend_observation"], "UPTREND_OBSERVED")
        self.assertEqual(result["decision"], "FLAT")
        self.assertEqual(result["risk_override"], "HALT")
        self.assertFalse(result["paper_execution_authorised"])
        self.assertFalse(result["live_execution_authorised"])
        self.assertEqual(result["candle_count"], 60)

    def test_downtrend_remains_halted(self):
        data = snapshot()
        for index, candle in enumerate(data["candles"]):
            base = 200 - index
            candle["open"] = str(base)
            candle["high"] = str(base + 2)
            candle["low"] = str(base - 1)
            candle["close"] = str(base + 1)
        result = research_report(data, now=NOW)
        self.assertEqual(result["trend_observation"], "DOWNTREND_OBSERVED")
        self.assertEqual(result["decision"], "FLAT")
        self.assertEqual(result["risk_override"], "HALT")
        self.assertFalse(result["paper_execution_authorised"])
        self.assertFalse(result["live_execution_authorised"])

    def test_account_data_is_rejected(self):
        data = snapshot()
        data["portfolio_id"] = "private"
        with self.assertRaises(ValueError):
            research_report(data, now=NOW)

    def test_bad_input_fails_closed(self):
        data = snapshot()
        data["candles"][-1]["complete"] = False
        with self.assertRaises(ValueError):
            research_report(data, now=NOW)

    def test_insufficient_history_fails_closed(self):
        data = snapshot()
        data["candles"] = data["candles"][-48:]
        with self.assertRaises(ValueError):
            research_report(data, now=NOW)


if __name__ == "__main__":
    unittest.main()
