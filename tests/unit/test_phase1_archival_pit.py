import unittest
from datetime import datetime, timedelta, timezone
from alpha_lab.research.phase1_archival_pit import verify_archival_availability


class ArchivalPITTests(unittest.TestCase):
    def setUp(self):
        self.decision = datetime(2025, 1, 3, 15, tzinfo=timezone.utc)
        self.kw = dict(
            decision_time=self.decision,
            publication_time=self.decision - timedelta(days=2),
            archive_capture_time=self.decision - timedelta(days=1),
            research_download_time=self.decision + timedelta(days=100),
            source_id="issuer-notice", content_sha256="a" * 64,
            archived_content_sha256="a" * 64,
            archive_provider="independent-archive", archive_record_id="record-001",
            publication_lag_seconds=60)

    def test_later_download_is_allowed_but_not_authenticated(self):
        r = verify_archival_availability(**self.kw)
        self.assertTrue(r["research_download_after_decision_permitted"])
        self.assertFalse(r["historical_availability_independently_proven"])
        self.assertFalse(r["eligible_for_strategy_promotion"])

    def test_future_archive_rejected(self):
        with self.assertRaisesRegex(ValueError, "after historical decision"):
            verify_archival_availability(**dict(self.kw, archive_capture_time=self.decision + timedelta(seconds=1)))

    def test_archive_before_publication_rejected(self):
        with self.assertRaisesRegex(ValueError, "precedes"):
            verify_archival_availability(**dict(self.kw, publication_time=self.decision))

    def test_content_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "differs"):
            verify_archival_availability(**dict(self.kw, archived_content_sha256="b" * 64))

    def test_naive_datetime_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            verify_archival_availability(**dict(self.kw, archive_capture_time=self.decision.replace(tzinfo=None)))

    def test_lag_rejected(self):
        with self.assertRaisesRegex(ValueError, "Publication lag"):
            verify_archival_availability(**dict(self.kw, publication_lag_seconds=3 * 86400))

    def test_missing_archive_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "archive_record_id"):
            verify_archival_availability(**dict(self.kw, archive_record_id=""))

    def test_download_before_archive_rejected(self):
        with self.assertRaisesRegex(ValueError, "predates"):
            verify_archival_availability(**dict(self.kw, research_download_time=self.decision - timedelta(days=3)))


if __name__ == "__main__":
    unittest.main()
