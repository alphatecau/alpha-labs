"""Evidence export with two years of synthetic archives, entirely offline."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest

from archive_fixture import make_archive, two_month_transport
from alpha_lab.data.adapters.binance_archive import build_dataset, month_range
from alpha_lab.research.evidence_export import export_evidence, SCHEMA
from alpha_lab.research.long_history import evaluate_spec, freeze_experiment


class EvidenceExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.base.cleanup)
        cls.data = Path(cls.base.name) / "datasets"
        assets = {}
        for year, month in month_range("2023-04", "2025-03"):
            assets.update(make_archive(year=year, month=month))
        built = build_dataset("BTCUSDT", "2023-04", "2025-03", cls.data, transport=assets.__getitem__)
        stem = "BTCUSDT-1h-2023-04_to_2025-03"
        spec = cls.data / "replay/experiments" / (stem + ".frozen.json")
        report = cls.data / "replay/reports" / (stem + ".report.json")
        freeze_experiment(Path(built["csv"]), Path(built["manifest"]), spec)
        evaluate_spec(Path(built["csv"]), Path(built["manifest"]), spec, report)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "datasets"
        shutil.copytree(self.data, self.root)
        self.output = Path(self.temp.name) / "complete.tar.gz"

    def export(self):
        return export_evidence(self.root, ["BTCUSDT"], "2023-04", "2025-03", self.output)

    def test_complete_bundle_contains_reproducible_inputs_and_source(self):
        result = self.export()
        self.assertEqual(result["reports_reproduced"], 1)
        self.assertEqual(result["sha256"], hashlib.sha256(self.output.read_bytes()).hexdigest())
        with tarfile.open(self.output, "r:gz") as archive:
            metadata = json.load(archive.extractfile("EVIDENCE_MANIFEST.json"))
            self.assertEqual(metadata["schema"], SCHEMA)
            self.assertFalse(metadata["trading_enabled"])
            self.assertFalse(metadata["independent_source_review_complete"])
            self.assertFalse(metadata["holdout_independently_sealed"])
            self.assertFalse(metadata["independent_price_verification"])
            self.assertTrue(metadata["reports_reproduced_locally"])
            self.assertTrue(all(not item["available"] for item in metadata["forensic_archives"]))
            self.assertIn("packages/alpha_lab/src/alpha_lab/research/long_history.py", metadata["files"])
            self.assertIn("datasets/curated/binance-vision/BTCUSDT-1h-2023-04_to_2025-03.manifest.json", metadata["files"])
            self.assertTrue(any(name.endswith(".CHECKSUM") for name in metadata["files"]))
            self.assertEqual(set(archive.getnames()), set(metadata["files"]) | {"EVIDENCE_MANIFEST.json"})
            for name, expected in metadata["files"].items():
                data = archive.extractfile(name).read()
                self.assertEqual(len(data), expected["bytes"])
                self.assertEqual(hashlib.sha256(data).hexdigest(), expected["sha256"])

    def test_modified_report_is_rejected_without_output(self):
        path = next((self.root / "replay/reports").glob("*.json"))
        report = json.loads(path.read_text())
        report["periods"]["test_unsealed"]["modelled_strategy"]["net_modelled_execution_return_pct"] += 1
        path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, "does not reproduce"):
            self.export()
        self.assertFalse(self.output.exists())

    def test_missing_archive_prevents_export(self):
        next((self.root / "raw").rglob("*.zip")).unlink()
        with self.assertRaises(FileNotFoundError):
            self.export()
        self.assertFalse(self.output.exists())

    def test_existing_bundle_is_preserved(self):
        self.output.write_bytes(b"keep this prior evidence")
        with self.assertRaises(FileExistsError):
            self.export()
        self.assertEqual(self.output.read_bytes(), b"keep this prior evidence")

    def test_rejected_forensic_archive_is_retained_with_its_error(self):
        assets = make_archive(year=2023, month=3, omit_hour=565)
        folder = self.root / "raw/binance-vision/spot-monthly-1h/BTCUSDT"
        for url, data in assets.items():
            (folder / url.rsplit("/", 1)[1]).write_bytes(data)
        self.export()
        with tarfile.open(self.output, "r:gz") as archive:
            metadata = json.load(archive.extractfile("EVIDENCE_MANIFEST.json"))
            march = metadata["forensic_archives"][1]
            self.assertTrue(march["available"])
            self.assertFalse(march["complete_hourly_grid"])
            self.assertIn("Missing, duplicated", march["structural_error"])
            self.assertIn("datasets/raw/binance-vision/spot-monthly-1h/BTCUSDT/BTCUSDT-1h-2023-03.zip", metadata["files"])

    def test_unsupported_or_repeated_symbols_are_rejected(self):
        for symbols in (["BTCUSDT", "BTCUSDT"], ["BTCUSD"], []):
            with self.subTest(symbols=symbols), self.assertRaises(ValueError):
                export_evidence(self.root, symbols, "2023-04", "2025-03", self.output)
        self.assertFalse(self.output.exists())

    def test_short_history_cannot_bypass_production_gate(self):
        root = Path(self.temp.name) / "short-datasets"
        transport, _ = two_month_transport()
        built = build_dataset("BTCUSDT", "2024-12", "2025-01", root, transport=transport)
        stem = "BTCUSDT-1h-2024-12_to_2025-01"
        spec = root / "replay/experiments" / (stem + ".frozen.json")
        freeze_experiment(Path(built["csv"]), Path(built["manifest"]), spec)
        report = root / "replay/reports" / (stem + ".report.json")
        report.parent.mkdir(parents=True)
        report.write_text('{"trading_enabled": false}')
        with self.assertRaisesRegex(ValueError, "Insufficient historical coverage"):
            export_evidence(root, ["BTCUSDT"], "2024-12", "2025-01", self.output)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
