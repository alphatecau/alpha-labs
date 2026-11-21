import base64
import hashlib
import json
import shutil
import tempfile
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from alpha_lab.research.live_paper_session import LivePaperSession
from alpha_lab.research.local_paper_recovery import verify_pair
from deployment.paper_aud import aud_result
from deployment.paper_site import RelayBudget, page_number
from deployment.paper_snapshot_reader import StoppedPaperSnapshotReader, configured_reader
from test_paper_commit_boundaries import ACCOUNT, FixedFeed, NOW, ORDER

OWNER = "oidc_" + "a" * 64
OTHER = "oidc_" + "b" * 64


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        session = LivePaperSession(self.root, ACCOUNT, FixedFeed(), clock=lambda: NOW)
        try:
            session.control("arm", expected_revision=session.state()["risk"]["revision"])
            session.order(ORDER)
            head = session.runtime.journal_head
        finally:
            session.close()
        self.raw = self.root / "alpha-paper.sqlite3"
        sha = hashlib.sha256(self.raw.read_bytes()).hexdigest()
        self.file = self.root / (sha + ".sqlite3")
        shutil.copyfile(self.raw, self.file)
        self.binding = {"account": ACCOUNT, "sha256": sha, "head": head, "sequence": 1,
                        "captured_at": NOW.isoformat()}
        self.fx = ({NOW.date() - timedelta(days=1): Decimal("0.65")}, "d" * 64)

    def reader(self, **changes):
        return StoppedPaperSnapshotReader({OWNER: {**self.binding, **changes}}, directory=self.root,
                                          fx_source=lambda: self.fx)

    def test_replay_backup_guard_and_aud(self):
        receipt = verify_pair(self.raw, self.file, expected_sequence=1, expected_head=self.binding["head"])
        self.assertEqual(receipt["backup_relationship"], "EXACT_FILL_HISTORY")
        reader = self.reader()
        data = reader.snapshot(OWNER)
        self.assertEqual(data["fills"][0]["order_id"], ORDER["order_id"])
        self.assertEqual(data["positions"], {"SOL-USD": "1"})
        self.assertEqual(Decimal(data["aud"]["fees"]), Decimal(data["fees_usd"]) / Decimal(".65"))
        self.assertEqual(data["execution"], "disabled")
        self.assertNotIn("account", data)
        self.assertEqual(reader.snapshot(OWNER, page=1)["fills"], [])
        with self.assertRaises(PermissionError):
            reader.snapshot(OTHER)
        with self.assertRaises(PermissionError):
            self.reader(account="a_different_local_owner").snapshot(OWNER)

    def test_tamper_checkpoint_and_separate_tenants(self):
        with self.assertRaises(ValueError):
            self.reader(sequence=2).snapshot(OWNER)
        with self.assertRaises(ValueError):
            StoppedPaperSnapshotReader({OWNER: self.binding, OTHER: self.binding}, directory=self.root)
        self.file.write_bytes(self.file.read_bytes() + b"x")
        with self.assertRaises(ValueError):
            self.reader().snapshot(OWNER)

    def test_render_secret_file_and_unavailable_fx(self):
        self.file.with_suffix(".b64").write_bytes(base64.b64encode(self.file.read_bytes()))
        self.file.unlink()
        self.assertIsNone(configured_reader({}))
        reader = configured_reader({"ALPHA_PAPER_JOURNAL_DIR": str(self.root),
                                    "ALPHA_PAPER_JOURNALS_JSON": json.dumps({OWNER: self.binding})})
        def offline():
            raise OSError("offline")
        reader.fx_source = offline
        data = reader.snapshot(OWNER)
        self.assertIsNone(data["aud"])
        self.assertIsNotNone(data["cash_usd"])

    def test_render_prefixed_secret_filename_and_tamper_rejection(self):
        encoded = self.root / ("j_" + self.binding["sha256"] + ".b64")
        encoded.write_bytes(base64.b64encode(self.file.read_bytes()))
        self.file.unlink()
        self.assertEqual(self.reader().snapshot(OWNER)["events"], 1)
        encoded.write_bytes(base64.b64encode(b"not the expected journal"))
        with self.assertRaises(ValueError):
            self.reader().snapshot(OWNER)

    def test_currency_dates_move_independently_of_usd_pnl(self):
        buy = {"symbol": "BTC-USD", "side": "BUY", "quantity": "2", "price": "100", "fee": "2",
               "filled_at": "2026-11-10T10:00:00Z"}
        sell = {**buy, "side": "SELL", "quantity": "1", "price": "120", "fee": "1",
                "filled_at": "2026-11-12T00:00:00Z"}
        rates = ({date(2026, 11, 9): Decimal("0.5"), date(2026, 11, 11): Decimal("0.8")}, "e" * 64)
        result = aud_result([buy, sell], {"cash_usd": "100", "nav_usd": "220"}, NOW, rates)
        self.assertEqual(Decimal(result["realised"]), Decimal("-53.25"))
        self.assertEqual(Decimal(result["unrealised"]), Decimal("-52"))
        self.assertEqual(Decimal(result["fees"]), Decimal("5.25"))
        with self.assertRaises(ValueError):
            aud_result([buy], {"cash_usd": "0", "nav_usd": "0"}, NOW + timedelta(days=10), rates)

    def test_read_budget_and_pagination(self):
        clock = [0]
        budget = RelayBudget(clock=lambda: clock[0], limit=1)
        self.assertTrue(budget.allow(OWNER))
        self.assertFalse(budget.allow(OWNER))
        self.assertTrue(budget.allow(OTHER))
        clock[0] = 61
        self.assertTrue(budget.allow(OWNER))
        self.assertEqual(page_number("page=3", True), 3)
        with self.assertRaises(ValueError):
            page_number("owner=other", True)
