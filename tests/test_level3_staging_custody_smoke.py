"""Staging custody smoke must never connect without explicit opt-in and broker DSN."""
import os
import unittest
from unittest.mock import patch
from tools.level3_staging.staging_custody_smoke import main


class StagingCustodySmokeSafetyTests(unittest.TestCase):
    def test_default_denied_without_network(self):
        with patch.dict(os.environ, {"LEVEL3_STAGING_CUSTODY_SMOKE": "", "LEVEL3_STAGING_BROKER_DSN": ""}):
            with self.assertRaisesRegex(SystemExit, "explicit synthetic staging authorisation"):
                main()

    def test_authorised_without_broker_credentials_denied(self):
        with patch.dict(os.environ, {"LEVEL3_STAGING_CUSTODY_SMOKE": "I_AUTHORISE_SYNTHETIC_STAGING_EVENT", "LEVEL3_STAGING_BROKER_DSN": ""}):
            with self.assertRaisesRegex(SystemExit, "dedicated staging broker DSN"):
                main()


if __name__ == "__main__":
    unittest.main()
