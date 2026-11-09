"""Deterministic, network-free EODHD adapter safety tests."""
import json
import os
import unittest
from unittest.mock import patch

from alpha_lab.data.eodhd_research import EODHDResearchError, parse_eodhd_eod

GOOD = json.dumps([{"date": "2025-01-02", "open": 100, "high": 105,
                    "low": 99, "close": 103, "volume": 2000}])


class EODHDResearchTests(unittest.TestCase):
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(EODHDResearchError):
                parse_eodhd_eod(GOOD, enabled=True)

    def test_requires_explicit_call_authorisation(self):
        with patch.dict(os.environ, {"ALPHA_EODHD_RESEARCH_ENABLED": "true"}):
            with self.assertRaises(EODHDResearchError):
                parse_eodhd_eod(GOOD)

    def test_valid_fixture_and_stable_hash(self):
        with patch.dict(os.environ, {"ALPHA_EODHD_RESEARCH_ENABLED": "true"}):
            bars, digest = parse_eodhd_eod(GOOD, enabled=True)
            self.assertEqual(len(bars), 1)
            self.assertEqual(len(digest), 64)
            self.assertEqual(digest, parse_eodhd_eod(GOOD, enabled=True)[1])

    def test_rejects_adversarial_data(self):
        bad = [
            "{}", "[]", "not json",
            json.dumps([{"date": "2025-01-02", "open": -1, "high": 105,
                         "low": 99, "close": 103, "volume": 2000}]),
            json.dumps([{"date": "2025-01-02", "open": 100, "high": 101,
                         "low": 99, "close": 103, "volume": 2000}]),
            GOOD[:-1] + ", " + GOOD[1:],
        ]
        with patch.dict(os.environ, {"ALPHA_EODHD_RESEARCH_ENABLED": "true"}):
            for payload in bad:
                with self.subTest(payload=payload[:30]):
                    with self.assertRaises(EODHDResearchError):
                        parse_eodhd_eod(payload, enabled=True)


if __name__ == "__main__":
    unittest.main()
