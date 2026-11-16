"""Offline security regression tests for the Coinbase research import boundary."""
import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from alpha_lab.research.coinbase_research_import import load_snapshot, validate_snapshot

NOW = datetime(2026, 11, 17, 8, tzinfo=timezone.utc)


def fixture(granularity="4h"):
    step = timedelta(hours=4) if granularity == "4h" else timedelta(days=1)
    end = NOW.replace(hour=8 if granularity == "4h" else 0)
    return {
        "schema_version": 1, "provider": "AlphaLabs Coinbase read-only",
        "product_id": "BTC-USD", "product_type": "SPOT", "quote_currency": "USD",
        "granularity": granularity, "collected_at": NOW.isoformat().replace("+00:00", "Z"),
        "candles": [{
            "start": (end - step * (48 - i)).isoformat().replace("+00:00", "Z"),
            "open": "100", "high": "110", "low": "90", "close": "105",
            "volume": "5", "complete": True,
        } for i in range(48)],
    }


class CoinbaseResearchImportTests(unittest.TestCase):
    def test_valid_closed_candles_are_research_only(self):
        for period in ("4h", "1d"):
            with self.subTest(period=period):
                result = validate_snapshot(fixture(period), now=NOW)
                self.assertEqual(result["status"], "VERIFIED_RESEARCH_ONLY")
                self.assertFalse(result["live_execution_authorised"])
                self.assertEqual(len(result["candles"]), 48)

    def test_rejects_bad_data_and_account_fields(self):
        cases = []
        for field, value in (("product_id", "DOGE-USD"), ("provider", "unknown"),
                             ("product_type", "GLOBAL_PERP"), ("quote_currency", "USDT")):
            x = fixture()
            x[field] = value
            cases.append(x)
        x = fixture()
        x["account_uuid"] = "secret"
        cases.append(x)
        x = fixture()
        x["candles"][1] = copy.deepcopy(x["candles"][0])
        cases.append(x)
        x = fixture()
        x["candles"][0]["complete"] = False
        cases.append(x)
        x = fixture()
        x["candles"][0]["high"] = "80"
        cases.append(x)
        x = fixture()
        x["candles"][0]["close"] = "NaN"
        cases.append(x)
        x = fixture()
        x["candles"][0]["volume"] = "-1"
        cases.append(x)
        x = fixture()
        x["candles"] = x["candles"][:12]
        cases.append(x)
        x = fixture()
        x["candles"][-1]["start"] = NOW.isoformat().replace("+00:00", "Z")
        cases.append(x)
        x = fixture()
        x["collected_at"] = (NOW - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        cases.append(x)
        x = fixture()
        x["collected_at"] = (NOW + timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
        cases.append(x)
        for index, bad in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(ValueError):
                validate_snapshot(bad, now=NOW)

    def test_local_file_and_no_execution_dependency(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "research.json"
            path.write_text(json.dumps(fixture()), encoding="utf-8")
            self.assertEqual(load_snapshot(path, now=NOW)["status"], "VERIFIED_RESEARCH_ONLY")
            path.unlink()
            with self.assertRaises(ValueError):
                load_snapshot(path, now=NOW)


if __name__ == "__main__":
    unittest.main()
