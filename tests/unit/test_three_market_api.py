"""Regression tests for the local read-only three-market API."""
import hashlib
import http.client
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Thread

from tools.local_research_server import MARKET_CONFIG, create_server


class ThreeMarketAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "apps/sites").mkdir(parents=True)
        (self.root / "apps/sites/index.html").write_text("TEST")

        self.now = datetime.now(timezone.utc)
        last = self.now - timedelta(hours=1)

        rows = ["timestamp,open,high,low,close,volume"]
        for i in range(720):
            stamp = last - timedelta(hours=719 - i)
            rows.append(f"{stamp.isoformat()},100,101,99,100,1")
        csv = ("\n".join(rows) + "\n").encode()
        digest = hashlib.sha256(csv).hexdigest()

        for slug, (pair, label) in MARKET_CONFIG.items():
            (self.root / f"{slug}-recent.csv").write_bytes(csv)
            manifest = {
                "requested_pair": pair,
                "interval_minutes": 60,
                "record_count": 720,
                "written_csv_sha256": digest,
                "fetched_at_utc": self.now.isoformat(),
                "last_complete_candle_utc": last.isoformat(),
            }
            metrics = {
                "strategy": {"return_pct": -1.0},
                "equal_allocation_buy_hold": {"return_pct": -2.0},
                "double_cost_strategy": {"return_pct": -1.5},
            }
            report = {
                "status": "HYPOTHESIS_SCREEN_ONLY_NOT_VALIDATED_ALPHA",
                "configuration_sha256": "c" * 64,
                "dataset": {
                    "sha256": digest,
                    "interval_minutes": 60,
                    "quote_currency": "USD",
                    "bars": 720,
                    "provenance": "kraken-public-ohlc",
                },
                "periods": {
                    "training": metrics,
                    "holdout": metrics,
                },
            }
            (self.root / f"{slug}-recent.csv.manifest.json").write_text(
                json.dumps(manifest)
            )
            (self.root / f"{slug}-research.json").write_text(
                json.dumps(report)
            )

        self.server = create_server(self.root, 0)
        self.thread = Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.thread.start()
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def request(self, method, path):
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=10
        )
        try:
            connection.request(method, path)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_all_three_markets_read_only(self):
        self.assertEqual(len(MARKET_CONFIG), 3)
        for slug, (_, label) in MARKET_CONFIG.items():
            with self.subTest(market=slug):
                status, data = self.request(
                    "GET", f"/api/v1/research/{slug}"
                )
                self.assertEqual(status, 200)
                self.assertEqual(data["market"], label)
                self.assertEqual(data["complete_candles"], 720)
                self.assertEqual(data["status"], "historical")
                self.assertIs(data["trading_enabled"], False)
                self.assertIn("holdout", data["periods"])

                status, _ = self.request(
                    "POST", f"/api/v1/research/{slug}"
                )
                self.assertEqual(status, 405)

    def test_tampered_data_fails_closed(self):
        path = self.root / "xbtusd-recent.csv"
        path.write_bytes(path.read_bytes() + b"tampered\n")
        status, data = self.request(
            "GET", "/api/v1/research/xbtusd"
        )
        self.assertEqual(status, 503)
        self.assertEqual(data["status"], "offline")

    def test_missing_market_data_fails_closed(self):
        (self.root / "ethusd-research.json").unlink()
        status, _ = self.request(
            "GET", "/api/v1/research/ethusd"
        )
        self.assertEqual(status, 503)

    def test_stale_market_data(self):
        path = self.root / "solusd-recent.csv.manifest.json"
        manifest = json.loads(path.read_text())
        manifest["fetched_at_utc"] = (
            self.now - timedelta(hours=8)
        ).isoformat()
        manifest["last_complete_candle_utc"] = (
            self.now - timedelta(hours=9)
        ).isoformat()
        path.write_text(json.dumps(manifest))
        status, data = self.request(
            "GET", "/api/v1/research/solusd"
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "stale")

    def test_invalid_requests(self):
        status, _ = self.request(
            "GET", "/api/v1/research/unknown"
        )
        self.assertEqual(status, 404)

        status, _ = self.request(
            "GET", "/api/v1/research/solusd?trade=true"
        )
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
