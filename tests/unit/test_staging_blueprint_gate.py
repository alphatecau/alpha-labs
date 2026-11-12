"""Fail-closed regression for the intentionally non-trading Render blueprint."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
BLUEPRINT = ROOT / "deployment/render-paper-staging.yaml"


class StagingBlueprintSafetyTests(unittest.TestCase):
    def test_diagnostic_cli_binds_only_loopback(self):
        probe = (ROOT / "deployment/staging_probe.py").read_text(encoding="utf-8")
        self.assertIn('make_server("127.0.0.1"', probe)
        self.assertNotIn('os.environ.get("HOST"', probe)
        self.assertNotIn('make_server("0.0.0.0"', probe)

    def test_staging_blueprint_does_not_enable_paper_orders(self):
        source = BLUEPRINT.read_text(encoding="utf-8")
        self.assertIn('startCommand: gunicorn --bind "0.0.0.0:$PORT" --workers 1 deployment.staging_probe:application', source)
        self.assertIn("autoDeploy: false", source)
        self.assertIn("healthCheckPath: /healthz", source)
        self.assertNotIn("key: HOST", source)
        self.assertIn('value: "false"', source)
        self.assertNotIn("paper_staging_wsgi:app", source)
        self.assertNotIn("ALPHA_PAPER_SIGNING_KEY_B64", source)
        self.assertNotIn("ALPHA_PAPER_OWNER_SUBJECT", source)
        self.assertNotIn("research/paper-first-copy-trading-gates-20261109", source)
        self.assertNotIn("disk:", source)
        self.assertNotIn("DATABASE_URL", source)


if __name__ == "__main__":
    unittest.main()
