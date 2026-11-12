"""Offline mocked provider boundary tests; never make network requests."""
from datetime import date
import json
import os
import unittest
from unittest.mock import patch

from alpha_lab.data.eodhd_client import ProviderReply, load_eodhd_research
from alpha_lab.data.eodhd_research import EODHDResearchError

GOOD = json.dumps([{"date":"2025-01-02","open":100,"high":105,
                    "low":99,"close":103,"volume":2000}])
START, END = date(2025, 1, 1), date(2025, 1, 31)
TOKEN = "SENSITIVE_TEST_TOKEN"


class EODHDClientTests(unittest.TestCase):
    def invoke(self, transport, **kwargs):
        return load_eodhd_research("SPY.US", START, END, api_token=TOKEN,
                                   transport=transport, **kwargs)

    def test_disabled_does_not_call_transport(self):
        called = []
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(EODHDResearchError):
                self.invoke(lambda *args: called.append(args), enabled=True)
        self.assertEqual(called, [])

    def test_explicit_authorisation_required(self):
        with patch.dict(os.environ, {"ALPHA_EODHD_RESEARCH_ENABLED": "true"}):
            with self.assertRaises(EODHDResearchError):
                self.invoke(lambda *_: ProviderReply(200, GOOD))

    def test_mocked_success_and_fixed_request(self):
        captured = []
        def fake(path, params):
            captured.append((path, params))
            return ProviderReply(200, GOOD)
        with patch.dict(os.environ, {"ALPHA_EODHD_RESEARCH_ENABLED": "true"}):
            bars, digest = self.invoke(fake, enabled=True)
        self.assertEqual(len(bars), 1)
        self.assertEqual(len(digest), 64)
        self.assertEqual(captured[0][0], "/api/eod/SPY.US")
        self.assertEqual(captured[0][1]["from"], "2025-01-01")

    def test_fail_closed_statuses_and_redaction(self):
        with patch.dict(os.environ, {"ALPHA_EODHD_RESEARCH_ENABLED": "true"}):
            for status in (401, 403, 429, 500, 302):
                with self.subTest(status=status):
                    with self.assertRaises(EODHDResearchError) as caught:
                        self.invoke(lambda *_: ProviderReply(status, TOKEN), enabled=True)
                    self.assertNotIn(TOKEN, str(caught.exception))
            with self.assertRaises(EODHDResearchError) as caught:
                self.invoke(lambda *_: (_ for _ in ()).throw(RuntimeError(TOKEN)), enabled=True)
            self.assertNotIn(TOKEN, str(caught.exception))

    def test_rejects_bad_symbol_and_out_of_range_data(self):
        with patch.dict(os.environ, {"ALPHA_EODHD_RESEARCH_ENABLED": "true"}):
            with self.assertRaises(EODHDResearchError):
                load_eodhd_research("../escape", START, END, api_token=TOKEN,
                    transport=lambda *_: ProviderReply(200, GOOD), enabled=True)
            with self.assertRaises(EODHDResearchError):
                load_eodhd_research("SPY.US", date(2025, 2, 1), date(2025, 2, 28),
                    api_token=TOKEN, transport=lambda *_: ProviderReply(200, GOOD), enabled=True)


if __name__ == "__main__":
    unittest.main()
