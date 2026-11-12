"""Adversarial SQLite snapshots with a synthetic independent authority."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alpha_lab.research.live_paper_session import LivePaperSession, PaperRejection
from alpha_lab.research.paper_checkpoint import seal_checkpoint, seal_state_checkpoint
from test_paper_commit_boundaries import FixedFeed, NOW, ORDER

OWNER = "oidc_" + "a" * 64
KEY = b"synthetic-state-checkpoint-key!!"


class SyntheticAuthority:
    owner_id = OWNER
    verification_key = KEY

    def __init__(self):
        self.rows = {}
        self.lose_confirmation = False

    def load(self):
        return self.rows[max(self.rows)][1] if self.rows else None

    def record(self, *, sequence, head, expected_sequence, expected_head):
        last = max(self.rows) if self.rows else None
        if (expected_sequence, expected_head) != (last, self.rows[last][0] if self.rows else None):
            raise PermissionError("stale authority")
        if sequence != (0 if last is None else last + 1):
            raise PermissionError("out-of-order checkpoint")
        envelope = seal_state_checkpoint(owner=OWNER, sequence=sequence, head=head, secret=KEY)
        self.rows[sequence] = (head, envelope)
        if self.lose_confirmation:
            raise ConnectionError("commit succeeded but reply lost")
        return envelope


class CompletePaperStateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "alpha-paper.sqlite3"
        self.authority = SyntheticAuthority()

    def open(self, *, provision=False):
        paper = LivePaperSession(self.directory.name, OWNER, FixedFeed(), clock=lambda: NOW,
                                 checkpoint_store=self.authority, provision=provision)
        self.addCleanup(paper.close)
        return paper

    @staticmethod
    def arm(paper):
        paper.control("arm", expected_revision=paper.state()["risk"]["revision"])

    def test_normal_start_never_enrols_missing_authority_or_overwrites_legacy_journal(self):
        with self.assertRaisesRegex(ValueError, "checkpoint missing"):
            self.open()
        self.assertFalse(self.path.exists())
        offline = LivePaperSession(self.directory.name, OWNER, FixedFeed(), clock=lambda: NOW)
        offline.close()
        with self.assertRaisesRegex(ValueError, "new journal"):
            self.open(provision=True)
        self.assertEqual(self.authority.rows, {})

    def test_prior_valid_guard_only_snapshot_rejected_without_a_fill(self):
        paper = self.open(provision=True)
        self.arm(paper)
        previous = paper.db.execute("SELECT * FROM paper_guard").fetchone()
        paper.control("halt")
        self.assertEqual(paper.runtime.ledger.sequence, 0)
        paper.close()
        with sqlite3.connect(self.path) as conn:
            conn.execute("DELETE FROM paper_guard")
            conn.execute("INSERT INTO paper_guard VALUES (?,?,?,?,?,?,?,?,?,?)", tuple(previous))
        with self.assertRaisesRegex(ValueError, "checkpoint mismatch"):
            self.open()

    def test_tampered_guard_ownership_replay_and_schema_are_rejected_before_writes(self):
        mutations = (
            ("UPDATE paper_guard SET daily_breach='', peak='99999'", ()),
            ("UPDATE paper_guard SET account=?", ("oidc_" + "b" * 64,)),
            ("INSERT INTO relay_nonces VALUES (?,?)", ("forged", 1)),
            ("CREATE TRIGGER sqliteX_trigger AFTER UPDATE ON paper_guard "
             "BEGIN UPDATE paper_guard SET enabled=1; END", ()),
        )
        paper = self.open(provision=True)
        self.arm(paper)
        with tempfile.TemporaryDirectory() as backup:
            saved = Path(backup) / "safe.sqlite3"
            with sqlite3.connect(saved) as conn:
                paper.db.backup(conn)
            paper.close()
            for sql, args in mutations:
                with self.subTest(sql=sql):
                    self.path.write_bytes(saved.read_bytes())
                    with sqlite3.connect(self.path) as conn:
                        conn.execute(sql, args)
                    with self.assertRaisesRegex(ValueError, "checkpoint mismatch"):
                        self.open()

    def test_checkpoint_replay_and_v1_envelopes_fail_closed(self):
        paper = self.open(provision=True)
        self.arm(paper)
        for envelope in (self.authority.rows[0][1], seal_checkpoint(sequence=0, head="0" * 64, secret=KEY)):
            with self.subTest(envelope=envelope[:20]), patch.object(self.authority, "load", return_value=envelope):
                paper.fault = False
                with self.assertRaises(PaperRejection) as denied:
                    paper.state()
                self.assertEqual((denied.exception.code, denied.exception.status), ("CHECKPOINT_HALT", 503))
                self.assertTrue(paper.runtime.ledger.halted)

    def test_partial_transaction_rolls_back_fill_and_control_snapshot(self):
        paper = self.open(provision=True)
        self.arm(paper)
        commit = paper._state_commitment

        def interrupt():
            if paper.runtime.ledger.sequence:
                raise OSError("write interrupted before SQLite commit")
            return commit()

        with patch.object(paper, "_state_commitment", side_effect=interrupt):
            with self.assertRaises(PaperRejection) as denied:
                paper.order(ORDER)
        self.assertEqual(denied.exception.code, "CHECKPOINT_HALT")
        paper.close()
        recovered = self.open()
        self.assertEqual(recovered.runtime.ledger.sequence, 0)
        self.assertFalse(recovered.state()["risk"]["armed"])

    def test_lost_commit_confirmation_recovers_only_exact_durable_pair(self):
        paper = self.open(provision=True)
        self.arm(paper)
        self.authority.lose_confirmation = True
        with self.assertRaises(PaperRejection) as denied:
            paper.order(ORDER)
        self.assertEqual(denied.exception.code, "CHECKPOINT_HALT")
        paper.close()
        self.authority.lose_confirmation = False
        recovered = self.open()
        self.assertFalse(recovered.state()["risk"]["armed"])
        self.assertEqual(recovered.order(ORDER)["status"], "ALREADY_COMMITTED")
        self.assertEqual(recovered.runtime.ledger.sequence, 1)

    def test_recovery_preserves_operator_halt_and_disallows_unanchored_open(self):
        paper = self.open(provision=True)
        self.arm(paper)
        paper.control("halt")
        paper.close()
        with self.assertRaisesRegex(ValueError, "without its authority"):
            LivePaperSession(self.directory.name, OWNER, FixedFeed(), clock=lambda: NOW)
        recovered = self.open()
        self.assertEqual(recovered.state()["risk"]["reason"], "OPERATOR_HALT")
        self.assertEqual(recovered.state()["recovery"]["status"], "VERIFIED")

    def test_pending_and_cancelled_orders_are_authenticated_without_fills(self):
        paper = self.open(provision=True)
        self.arm(paper)
        intent = {**ORDER, "order_type": "LIMIT", "limit_price": "99"}
        self.assertEqual(paper.order(intent)["status"], "PENDING")
        paper.cancel({"order_id": intent["order_id"]})
        self.assertEqual(paper.runtime.ledger.sequence, 0)
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE paper_orders SET status='PENDING'")
        with self.assertRaises(PaperRejection) as denied:
            paper.order(intent)
        self.assertEqual(denied.exception.code, "CHECKPOINT_HALT")
