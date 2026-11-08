"""Offline research runner preflight tests; never access public networks."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.breakout_archive_research import main

class BreakoutArchiveRunnerTests(unittest.TestCase):
    def test_missing_manifest_fails_before_any_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/"reports"
            argv = ["breakout_archive_research.py", "--data-root", tmp,
                    "--output-root", str(output), "--start-index", "840",
                    "--end-index", "1000", "--symbols", "BTCUSDT"]
            with patch.object(sys, "argv", argv):
                with self.assertRaises(FileNotFoundError):
                    main()
            self.assertFalse(output.exists())

    def test_rejects_duplicate_symbols(self):
        with tempfile.TemporaryDirectory() as tmp:
            argv = ["breakout_archive_research.py", "--data-root", tmp,
                    "--output-root", str(Path(tmp)/"reports"),
                    "--start-index", "840", "--end-index", "1000",
                    "--symbols", "BTCUSDT", "BTCUSDT"]
            with patch.object(sys, "argv", argv):
                with self.assertRaises(SystemExit) as caught:
                    main()
            self.assertEqual(caught.exception.code, 2)

    def test_rejects_short_warmup(self):
        with tempfile.TemporaryDirectory() as tmp:
            argv = ["breakout_archive_research.py", "--data-root", tmp,
                    "--output-root", str(Path(tmp)/"reports"),
                    "--start-index", "100", "--end-index", "1000"]
            with patch.object(sys, "argv", argv):
                with self.assertRaises(SystemExit) as caught:
                    main()
            self.assertEqual(caught.exception.code, 2)

if __name__ == "__main__":
    unittest.main()
