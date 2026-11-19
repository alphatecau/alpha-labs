"""No-credential preflight must exit before network access."""
import os
import unittest
from unittest.mock import patch
from tools.level3_staging.auditor_android_preflight import main


class AuditorAndroidPreflightTests(unittest.TestCase):
    def test_missing_dsn_fails_closed(self):
        with patch.dict(os.environ, {"LEVEL3_AUDITOR_READONLY_DSN": ""}):
            with self.assertRaisesRegex(SystemExit, "BLOCKED"):
                main()


if __name__ == "__main__":
    unittest.main()
