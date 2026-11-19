"""Fail-closed entrypoint checks without contacting Neon or Google Drive."""
import os
import unittest
from unittest.mock import patch

from tools.level3_staging.auditor_android_checkpoint import main


class AuditorAndroidCheckpointTests(unittest.TestCase):
    def test_missing_readonly_dsn_denied_before_key_or_network(self):
        with patch.dict(os.environ, {"LEVEL3_AUDITOR_READONLY_DSN": ""}):
            with self.assertRaisesRegex(SystemExit, "BLOCKED"):
                main()

    def test_missing_readonly_dsn_does_not_create_auditor_store(self):
        with patch.dict(os.environ, {"LEVEL3_AUDITOR_READONLY_DSN": ""}):
            with patch("pathlib.Path.mkdir", side_effect=AssertionError("unexpected write")):
                with self.assertRaisesRegex(SystemExit, "BLOCKED"):
                    main()


if __name__ == "__main__":
    unittest.main()
