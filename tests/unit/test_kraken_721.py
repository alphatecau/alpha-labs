import unittest
from datetime import datetime, timezone
from alpha_lab.data.adapters.kraken_ohlc import parse_ohlc_payload

class Kraken721Tests(unittest.TestCase):
    def test_721_accepted_722_rejected(self):
        start = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
        candles = [
            [start + i*3600, "100", "101", "99", "100", "0", "1", 2]
            for i in range(721)
        ]
        payload = {"error": [], "result": {"SOLUSD": candles, "last": 0}}
        rows, _ = parse_ohlc_payload(payload, pair="SOLUSD", minutes=60)
        self.assertEqual(len(rows), 720)
        self.assertEqual(
            rows[-1][0],
            datetime.fromtimestamp(candles[-2][0], timezone.utc).isoformat()
        )
        candles.append(candles[-1].copy())
        with self.assertRaisesRegex(ValueError, "limit"):
            parse_ohlc_payload(payload, pair="SOLUSD", minutes=60)
