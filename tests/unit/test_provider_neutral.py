"""Deterministic, offline provider-neutral foundation regression tests."""
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from alpha_lab.data.provider_neutral import load_offline_dataset, verify_offline_dataset

UTC = timezone.utc


class ProviderNeutralTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "synthetic.csv"
        self.rows = []
        for i in range(80):
            stamp = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(hours=i)
            self.rows.append([stamp.isoformat(), "100", "105", "99", "102", "10"])
        self.write()

    def write(self):
        with self.path.open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
            writer.writerows(self.rows)

    def load(self):
        return load_offline_dataset(
            self.path, quote_currency="USDC", interval_minutes=60,
            source_class="synthetic", source_id="fixture-001",
            venue="synthetic", instrument="SOLUSDC",
            retrieved_at_utc="2025-01-05T00:00:00+00:00")

    def test_canonical_and_manifest_roundtrip(self):
        result = self.load()
        self.assertEqual(len(result.bars), 80)
        self.assertEqual(result.bars[0].timestamp_utc.tzinfo, UTC)
        self.assertFalse(result.verified_prices)
        self.assertFalse(result.trading_enabled)
        verify_offline_dataset(self.path, result)
        self.assertEqual(result.provenance_digest, self.load().provenance_digest)

    def test_rejects_tampering(self):
        result = self.load()
        self.rows[2][4] = "103"
        self.write()
        with self.assertRaises(ValueError):
            verify_offline_dataset(self.path, result)

    def test_fail_closed_bad_bars(self):
        for index, value in ((2, "NaN"), (3, "-1"), (1, "0")):
            original = self.rows[5][index]
            self.rows[5][index] = value
            self.write()
            with self.subTest(index=index, value=value), self.assertRaises(ValueError):
                self.load()
            self.rows[5][index] = original

    def test_rejects_manifest_metadata_tampering(self):
        from dataclasses import replace
        result = self.load()
        for field, value in (("instrument", "BTCUSDT"), ("source_class", "exchange-public"),
                             ("retrieved_at_utc", "2025-01-06T00:00:00+00:00")):
            altered = dict(result.manifest)
            altered[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify_offline_dataset(self.path, replace(result, manifest=altered))

    def test_rejects_inflated_price_and_trading_claims(self):
        from dataclasses import replace
        result = self.load()
        with self.assertRaises(ValueError):
            verify_offline_dataset(self.path, replace(result, verified_prices=True))
        with self.assertRaises(ValueError):
            verify_offline_dataset(self.path, replace(result, trading_enabled=True))
        altered = dict(result.manifest)
        altered["price_source_authenticated"] = True
        with self.assertRaises(ValueError):
            verify_offline_dataset(self.path, replace(result, manifest=altered))

    def test_rejects_changed_canonical_observations(self):
        from dataclasses import replace
        result = self.load()
        altered = replace(result, bars=result.bars[:-1])
        with self.assertRaises(ValueError):
            verify_offline_dataset(self.path, altered)

    def test_rejects_duplicate_gap_and_future_retrieval(self):
        original = self.rows[8][0]
        for stamp in (self.rows[7][0], "2025-01-01T09:30:00+00:00"):
            self.rows[8][0] = stamp
            self.write()
            with self.assertRaises(ValueError):
                self.load()
        self.rows[8][0] = original
        self.write()
        with self.assertRaises(ValueError):
            load_offline_dataset(
                self.path, quote_currency="USDC", interval_minutes=60,
                source_class="synthetic", source_id="fixture-001",
                venue="synthetic", instrument="SOLUSDC",
                retrieved_at_utc="2025-01-01T00:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
