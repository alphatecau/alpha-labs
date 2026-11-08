import unittest
from datetime import datetime, timedelta, timezone
from alpha_lab.research.phase1_pit_availability import verify_evidence_available


class PITAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.decision = datetime(2025, 1, 3, 15, tzinfo=timezone.utc)
        self.kw = dict(decision_time=self.decision,
                       publication_time=self.decision - timedelta(hours=2),
                       retrieved_time=self.decision - timedelta(hours=1),
                       source_id="official-action-feed", immutable_sha256="a" * 64,
                       required_lag_seconds=60)

    def test_valid_timestamps_do_not_claim_authentication(self):
        r = verify_evidence_available(**self.kw)
        self.assertTrue(r["available_for_decision_by_supplied_timestamps"])
        self.assertFalse(r["publication_independently_authenticated"])
        self.assertFalse(r["eligible_for_strategy_promotion"])

    def test_future_publication_rejected(self):
        with self.assertRaisesRegex(ValueError, "published after"):
            verify_evidence_available(**dict(self.kw, publication_time=self.decision + timedelta(seconds=1)))

    def test_lag_boundary_rejected(self):
        with self.assertRaisesRegex(ValueError, "published after"):
            verify_evidence_available(**dict(self.kw, publication_time=self.decision - timedelta(seconds=59)))

    def test_post_decision_retrieval_rejected(self):
        with self.assertRaisesRegex(ValueError, "acquired after"):
            verify_evidence_available(**dict(self.kw, retrieved_time=self.decision + timedelta(seconds=1)))

    def test_retrieval_before_publication_rejected(self):
        with self.assertRaisesRegex(ValueError, "precedes"):
            verify_evidence_available(**dict(self.kw, retrieved_time=self.decision - timedelta(hours=3)))

    def test_naive_timestamp_rejected(self):
        with self.assertRaisesRegex(ValueError, "Timezone-aware"):
            verify_evidence_available(**dict(self.kw, decision_time=self.decision.replace(tzinfo=None)))

    def test_invalid_hash_and_lag_rejected(self):
        for bad in ("", "x" * 64, "a" * 63):
            with self.subTest(hash=bad), self.assertRaisesRegex(ValueError, "hash"):
                verify_evidence_available(**dict(self.kw, immutable_sha256=bad))
        with self.assertRaisesRegex(ValueError, "lag"):
            verify_evidence_available(**dict(self.kw, required_lag_seconds=-1))


if __name__ == "__main__":
    unittest.main()
