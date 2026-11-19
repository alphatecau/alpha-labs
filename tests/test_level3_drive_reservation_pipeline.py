import unittest
from unittest.mock import patch

from tools.level3_staging.drive_reservation_pipeline import reserved_upload_and_verify


class ReservationPipelineTests(unittest.TestCase):
    @patch("tools.level3_staging.drive_reservation_pipeline.complete_reservation")
    @patch("tools.level3_staging.drive_reservation_pipeline.upload_and_verify")
    @patch("tools.level3_staging.drive_reservation_pipeline.reserve")
    def test_success_order(self, reserve, upload, complete):
        upload.return_value = {"name": "a" * 64 + ".bin", "parent_id": "folder", "file_id": "file"}
        with patch("tools.level3_staging.drive_reservation_pipeline.hashlib.sha256") as sha:
            sha.return_value.hexdigest.return_value = "a" * 64
            reserved_upload_and_verify(object(), object(), "folder", b"ciphertext")
        self.assertEqual(reserve.call_count, 1)
        self.assertEqual(upload.call_count, 1)
        self.assertEqual(complete.call_count, 1)

    @patch("tools.level3_staging.drive_reservation_pipeline.complete_reservation")
    @patch("tools.level3_staging.drive_reservation_pipeline.upload_and_verify")
    @patch("tools.level3_staging.drive_reservation_pipeline.reserve")
    def test_failed_upload_leaves_reservation(self, reserve, upload, complete):
        upload.side_effect = RuntimeError("Drive unavailable")
        with self.assertRaisesRegex(RuntimeError, "Drive unavailable"):
            reserved_upload_and_verify(object(), object(), "folder", b"ciphertext")
        reserve.assert_called_once()
        complete.assert_not_called()

    @patch("tools.level3_staging.drive_reservation_pipeline.complete_reservation")
    @patch("tools.level3_staging.drive_reservation_pipeline.upload_and_verify")
    @patch("tools.level3_staging.drive_reservation_pipeline.reserve")
    def test_receipt_mismatch_blocks_completion(self, reserve, upload, complete):
        upload.return_value = {"name": "wrong.bin", "parent_id": "folder", "file_id": "file"}
        with self.assertRaisesRegex(ValueError, "receipt identity mismatch"):
            reserved_upload_and_verify(object(), object(), "folder", b"ciphertext")
        complete.assert_not_called()

    @patch("tools.level3_staging.drive_reservation_pipeline.complete_reservation")
    @patch("tools.level3_staging.drive_reservation_pipeline.upload_and_verify")
    @patch("tools.level3_staging.drive_reservation_pipeline.reserve")
    def test_reservation_failure_blocks_cloud_upload(self, reserve, upload, complete):
        reserve.side_effect = RuntimeError("conflict")
        with self.assertRaisesRegex(RuntimeError, "conflict"):
            reserved_upload_and_verify(object(), object(), "folder", b"ciphertext")
        upload.assert_not_called()
        complete.assert_not_called()

    def test_non_bytes_denied(self):
        with self.assertRaisesRegex(ValueError, "payload must be bytes"):
            reserved_upload_and_verify(object(), object(), "folder", "plaintext")
