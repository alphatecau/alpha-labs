import csv
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from alpha_lab.data.equity_csv import load_equity_csv
from alpha_lab.data.equity_provenance import (
    build_manifest, verify_manifest
)
from alpha_lab.data.exchange_calendar_2026 import sessions_2026
from alpha_lab.domain.assets import AssetClass, Instrument


class EquityProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "aapl.csv"
        self.start = date(2026, 11, 25)
        self.end = date(2026, 11, 27)
        self.instrument = Instrument(
            "AAPL", AssetClass.US_EQUITY, "XNAS", "USD", "XNAS"
        )
        with self.path.open("w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(
                ["timestamp", "open", "high", "low", "close", "volume"]
            )
            for session in sessions_2026("XNAS", self.start, self.end):
                count = int(
                    (session.closes_utc - session.opens_utc)
                    / timedelta(minutes=30)
                )
                for i in range(count):
                    stamp = session.opens_utc + timedelta(minutes=30*i)
                    writer.writerow(
                        [stamp.isoformat(), 100, 102, 99, 101, 1000]
                    )

    def manifest(self, basis="unknown"):
        imported = load_equity_csv(
            self.path, instrument=self.instrument,
            start=self.start, end=self.end,
            source_id="offline-test-fixture",
            retrieved_at_utc=datetime(
                2026, 11, 28, tzinfo=timezone.utc
            ),
        )
        return build_manifest(
            imported, source_reference="synthetic-local-test",
            price_basis=basis,
        )

    def test_manifest_verification(self):
        record = self.manifest()
        self.assertEqual(
            verify_manifest(self.path, record), record
        )
        self.assertEqual(record["candle_count"], 20)

    def test_verification_flags_remain_false(self):
        record = self.manifest()
        self.assertFalse(record["research_admissible"])
        self.assertFalse(record["source_authenticity_verified"])
        self.assertFalse(record["corporate_actions_verified"])
        self.assertFalse(record["trading_enabled"])

    def test_file_tampering_detected(self):
        record = self.manifest()
        content = self.path.read_text()
        changed = content.replace(",101,1000", ",100,1000", 1)
        self.assertNotEqual(content, changed)
        self.path.write_text(changed)
        with self.assertRaises(ValueError):
            verify_manifest(self.path, record)

    def test_metadata_tampering_detected(self):
        record = self.manifest()
        record["source_reference"] = "different-source"
        with self.assertRaises(ValueError):
            verify_manifest(self.path, record)

    def test_false_assurance_rejected(self):
        record = self.manifest()
        record["corporate_actions_verified"] = True
        with self.assertRaises(ValueError):
            verify_manifest(self.path, record)

    def test_unknown_price_basis_rejected(self):
        with self.assertRaises(ValueError):
            self.manifest("guaranteed-adjusted")


if __name__ == "__main__":
    unittest.main()
