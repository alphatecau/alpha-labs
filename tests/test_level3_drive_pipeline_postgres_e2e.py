"""Real disposable PostgreSQL + in-memory Drive adapter end-to-end checks.

Proves orchestration and DB state, NOT Google Drive OAuth or external signing.
"""
import hashlib
import os
import unittest
import uuid
from pathlib import Path

from tools.level3_staging.drive_reservation_pipeline import reserved_upload_and_verify
from tools.level3_staging.drive_upload_reservation import UploadReservationDenied


class FakeDrive:
    def __init__(self, corrupt=False):
        self.objects = []
        self.corrupt = corrupt
        self.create_calls = 0

    def find_by_name(self, parent_id, name):
        return [o["metadata"] for o in self.objects if o["metadata"]["parents"] == [parent_id] and o["metadata"]["name"] == name]

    def create(self, parent_id, name, payload):
        self.create_calls += 1
        metadata = {"id": "ci-file-" + str(self.create_calls), "name": name, "parents": [parent_id], "trashed": False}
        self.objects.append({"metadata": metadata, "payload": payload})
        return metadata

    def download(self, file_id):
        data = next(o["payload"] for o in self.objects if o["metadata"]["id"] == file_id)
        return data + b"tampered" if self.corrupt else data


@unittest.skipUnless(os.environ.get("LEVEL3_TEST_POSTGRES_DSN"), "disposable CI database required")
class PostgresDrivePipelineE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        cls.conn = psycopg.connect(os.environ["LEVEL3_TEST_POSTGRES_DSN"], autocommit=True)
        if cls.conn.execute("SELECT current_database()").fetchone()[0] != "level3_ci_test":
            cls.conn.close()
            raise RuntimeError("refusing non-disposable database")
        cls.conn.execute("CREATE SCHEMA IF NOT EXISTS level3_custody")
        cls.conn.execute(Path("docs/LEVEL3_DRIVE_RESERVATION_STAGING.sql").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def _state(self, parent, digest):
        return self.conn.execute(
            "SELECT state,file_id,verified_at FROM level3_custody.drive_upload_reservation WHERE parent_id=%s AND sha256=%s",
            (parent, digest),
        ).fetchone()

    def test_reserve_upload_readback_commit_and_duplicate_denial(self):
        parent = "ci-e2e-" + uuid.uuid4().hex
        payload = b"synthetic-custody-" + uuid.uuid4().bytes
        digest = hashlib.sha256(payload).hexdigest()
        drive = FakeDrive()
        receipt = reserved_upload_and_verify(self.conn, drive, parent, payload)
        self.assertEqual(receipt["sha256"], digest)
        self.assertEqual(receipt["file_id"], "ci-file-1")
        state = self._state(parent, digest)
        self.assertEqual(state[0], "verified")
        self.assertEqual(state[1], receipt["file_id"])
        self.assertIsNotNone(state[2])
        with self.assertRaises(UploadReservationDenied):
            reserved_upload_and_verify(self.conn, drive, parent, payload)
        self.assertEqual(drive.create_calls, 1)

    def test_corrupt_readback_keeps_reservation_pending(self):
        parent = "ci-e2e-" + uuid.uuid4().hex
        payload = b"synthetic-fault-" + uuid.uuid4().bytes
        digest = hashlib.sha256(payload).hexdigest()
        drive = FakeDrive(corrupt=True)
        with self.assertRaises(ValueError):
            reserved_upload_and_verify(self.conn, drive, parent, payload)
        self.assertEqual(self._state(parent, digest), ("reserved", None, None))
        with self.assertRaises(UploadReservationDenied):
            reserved_upload_and_verify(self.conn, drive, parent, payload)
        self.assertEqual(drive.create_calls, 1)


if __name__ == "__main__":
    unittest.main()
