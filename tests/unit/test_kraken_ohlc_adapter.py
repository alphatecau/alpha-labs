import unittest
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from alpha_lab.data.adapters.kraken_ohlc import (
    parse_ohlc_payload,
    write_csv_and_manifest,
)


class KrakenAdapterTests(unittest.TestCase):
    def sample(self):
        st = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
        candles = []
        for i in range(100):
            price = 100 + i
            candles.append(
                [
                    st + i * 3600,
                    str(price),
                    str(price + 1),
                    str(price - 1),
                    str(price),
                    "ignored",
                    "3",
                    2,
                ]
            )
        return {"error": [], "result": {"XSOLZUSD": candles, "last": st + 100 * 3600}}

    def test_drop_unfinished_last(self):
        rows, key = parse_ohlc_payload(self.sample(), pair="SOLUSD", minutes=60)
        self.assertEqual(key, "XSOLZUSD")
        self.assertEqual(len(rows), 99)
        self.assertEqual(rows[-1][1], "198")

    def test_bad_pair(self):
        with self.assertRaises(ValueError):
            parse_ohlc_payload(self.sample(), pair="FOOUSD", minutes=60)

    def test_exchange_error(self):
        with self.assertRaises(ValueError):
            parse_ohlc_payload(
                {"error": ["Bad pair"], "result": {}}, pair="SOLUSD", minutes=60
            )

    def test_no_series(self):
        with self.assertRaises(ValueError):
            parse_ohlc_payload(
                {"error": [], "result": {"last": 123}}, pair="SOLUSD", minutes=60
            )

    def test_write_manifest_and_validate(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "data.csv"
            m = write_csv_and_manifest(
                self.sample(), "a" * 64, pair="SOLUSD", minutes=60, output=f
            )
            self.assertEqual(m["record_count"], 99)
            self.assertTrue(m["unfinished_final_candle_removed"])
            self.assertTrue(f.exists())
            self.assertTrue(f.with_suffix(".csv.manifest.json").exists())

    def test_fail_closed_on_gaps(self):
        data = self.sample()
        data["result"]["XSOLZUSD"].pop(50)
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "data.csv"
            with self.assertRaisesRegex(ValueError, "irregular"):
                write_csv_and_manifest(
                    data, "a" * 64, pair="SOLUSD", minutes=60, output=f
                )
            self.assertFalse(f.exists())


if __name__ == "__main__":
    unittest.main()
