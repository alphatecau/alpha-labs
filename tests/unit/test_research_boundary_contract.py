"""Contract tests prevent research-only API/UI approval drift.

These are static source-contract checks, not browser or production deployment tests.
"""
import unittest
from pathlib import Path

from tools.local_research_server import load_snapshot


ROOT = Path(__file__).resolve().parents[2]


class ResearchBoundaryContractTests(unittest.TestCase):
    def test_ui_requires_explicit_denials_in_both_read_only_views(self):
        source = (ROOT / "apps/sites/research-bridge.js").read_text(encoding="utf-8")
        for key in ("promotion_authorised", "live_trading_authorised"):
            self.assertGreaterEqual(source.count(key + " !== false"), 2)

    def test_server_is_read_only_and_binds_loopback(self):
        source = (ROOT / "tools/local_research_server.py").read_text(encoding="utf-8")
        self.assertIn('ThreadingHTTPServer(("127.0.0.1", port)', source)
        self.assertIn('self._send_json(405, {"status": "read_only"})', source)

    def test_no_approval_from_report_forged_flags(self):
        # Existing integration tests construct a valid synthetic snapshot;
        # this test guards against source contract regressions at the boundary.
        source = (ROOT / "tools/local_research_server.py").read_text(encoding="utf-8")
        self.assertIn('"promotion_authorised": False', source)
        self.assertIn('"live_trading_authorised": False', source)


if __name__ == "__main__":
    unittest.main()
