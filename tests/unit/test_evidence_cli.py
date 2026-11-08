import csv
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from alpha_lab.research.evidence_cli import run_export, main

class EvidenceCliTests(unittest.TestCase):
    def make_csv(self, folder):
        path = folder / "candles.csv"
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        with path.open("w", newline="", encoding="utf-8") as fp:
            writer = csv.writer(fp)
            writer.writerow(("timestamp", "open", "high", "low", "close", "volume"))
            for i in range(240):
                price = 100 + i % 17
                writer.writerow(((start + timedelta(hours=i)).isoformat(),
                                 price, price + 1, price - 1, price, 100))
        return path

    def test_cli_writes_reproducible_timestamped_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = self.make_csv(root)
            one, two = root / "one.json", root / "two.json"
            args = dict(start=100, end=220, fold_id="fold-1",
                        provenance="synthetic-test", code_revision="fixture")
            first = run_export(csv_path, one, **args)
            second = run_export(csv_path, two, **args)
            self.assertEqual(first, second)
            self.assertEqual(json.loads(one.read_text()), first)
            self.assertEqual(len(first["periods"]), 120)
            self.assertEqual(first["modelled_order_count"], len(first["orders"]))
            self.assertFalse(first["holdout_independently_sealed"])

    def test_does_not_overwrite_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_csv(root)
            target = root / "evidence.json"
            target.write_text("existing")
            with self.assertRaises(FileExistsError):
                run_export(source, target, start=100, end=220, fold_id="f")
            self.assertEqual(target.read_text(), "existing")

    def test_rejects_input_as_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.make_csv(Path(tmp))
            with self.assertRaises(ValueError):
                run_export(source, source, start=100, end=220, fold_id="f")

    def test_command_line_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_csv(root)
            target = root / "output.json"
            self.assertEqual(main([str(source), "--output", str(target),
                                   "--start", "100", "--end", "220",
                                   "--fold-id", "fold-1"]), 0)
            self.assertTrue(target.exists())

if __name__ == "__main__":
    unittest.main()
