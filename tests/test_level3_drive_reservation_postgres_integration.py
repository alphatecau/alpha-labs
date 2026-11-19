"""Real PostgreSQL reservation tests, restricted to disposable GitHub CI database."""
import hashlib
import os
import unittest
import uuid
from pathlib import Path

from tools.level3_staging.drive_upload_reservation import (
    UploadReservationDenied,
    complete_reservation,
    reserve,
)


@unittest.skipUnless(os.environ.get("LEVEL3_TEST_POSTGRES_DSN"), "isolated test DSN required")
class DriveReservationPostgresIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg

        cls.conn = psycopg.connect(os.environ["LEVEL3_TEST_POSTGRES_DSN"], autocommit=True)
        db = cls.conn.execute("SELECT current_database()").fetchone()[0]
        if db != "level3_ci_test":
            cls.conn.close()
            raise RuntimeError("refusing migration outside disposable CI database")
        cls.conn.execute("CREATE SCHEMA IF NOT EXISTS level3_custody")
        cls.conn.execute(Path("docs/LEVEL3_DRIVE_RESERVATION_STAGING.sql").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_exclusive_claim_and_completion(self):
        digest = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
        owner = uuid.uuid4().hex
        parent = "ci-folder-" + uuid.uuid4().hex
        self.assertEqual(reserve(self.conn, parent, digest, owner)["state"], "reserved")
        with self.assertRaises(UploadReservationDenied):
            reserve(self.conn, parent, digest, uuid.uuid4().hex)
        with self.assertRaises(UploadReservationDenied):
            complete_reservation(self.conn, parent, digest, uuid.uuid4().hex, "file")
        self.assertEqual(
            complete_reservation(self.conn, parent, digest, owner, "file")["state"],
            "verified",
        )
        with self.assertRaises(UploadReservationDenied):
            complete_reservation(self.conn, parent, digest, owner, "file")

    def test_separate_connections_compete_for_unique_key(self):
        import psycopg

        digest = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
        parent = "ci-folder-" + uuid.uuid4().hex
        with psycopg.connect(os.environ["LEVEL3_TEST_POSTGRES_DSN"], autocommit=True) as other:
            reserve(self.conn, parent, digest, uuid.uuid4().hex)
            with self.assertRaises(UploadReservationDenied):
                reserve(other, parent, digest, uuid.uuid4().hex)

    def test_invalid_owner_rejected_before_sql(self):
        with self.assertRaises(UploadReservationDenied):
            reserve(self.conn, "ci-folder", "a" * 64, "not-a-token")
