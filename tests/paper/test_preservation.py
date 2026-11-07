import hashlib
import json
from pathlib import Path
import unittest
from alpha_lab.paper.committee import REJECTED
from alpha_lab.paper.cli import replay
from alpha_lab.paper.contracts import canonical
from fixtures import ALICE,NOW,proposal,quote

ROOT=Path(__file__).resolve().parents[2]


class PreservationTests(unittest.TestCase):
    def test_baseline_research_risk_ui_data_and_evidence_bytes_preserved(self):
        manifest=json.loads((ROOT/'docs/evidence/v0.12/baseline-preservation.json').read_text())
        for path,expected in manifest['sha256'].items():
            with self.subTest(path=path):
                self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),expected)

    def test_synthetic_replay_is_byte_reproducible_and_bob_untouched(self):
        a=replay();b=replay()
        self.assertEqual(canonical(a),canonical(b))
        self.assertEqual(a['bob']['cash'],'10000')
        self.assertEqual(a['fill_count'],2)
        self.assertTrue(a['reconciliation']['ok'])
        self.assertTrue(a['alice']['halted'])
        self.assertFalse(a['live_trading_enabled'])
