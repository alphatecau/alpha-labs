import unittest

from tools.level3_staging.drive_upload_reservation import (
    UploadReservationDenied,
    complete_reservation,
    reserve,
)


class FakeConnection:
    def __init__(self):
        self.rows = {}
        self.transaction_count = 0

    def transaction(self):
        connection = self

        class Transaction:
            def __enter__(self):
                connection.transaction_count += 1

            def __exit__(self, *_args):
                return False

        return Transaction()

    def execute(self, query, args):
        connection = self

        class Result:
            def fetchone(self):
                if query.startswith("INSERT"):
                    parent, digest, owner = args
                    key = (parent, digest)
                    if key in connection.rows:
                        return None
                    connection.rows[key] = ("reserved", owner, None)
                    return (owner,)
                file_id, parent, digest, owner = args
                key = (parent, digest)
                if connection.rows.get(key) != ("reserved", owner, None):
                    return None
                connection.rows[key] = ("verified", owner, file_id)
                return (file_id,)

        return Result()


class ReservationTests(unittest.TestCase):
    def setUp(self):
        self.conn = FakeConnection()
        self.digest = "a" * 64
        self.owner = "b" * 32

    def test_reserve_and_complete(self):
        self.assertEqual(reserve(self.conn, "folder", self.digest, self.owner)["state"], "reserved")
        self.assertEqual(
            complete_reservation(self.conn, "folder", self.digest, self.owner, "file")["state"],
            "verified",
        )

    def test_competing_worker_denied(self):
        reserve(self.conn, "folder", self.digest, self.owner)
        with self.assertRaisesRegex(UploadReservationDenied, "already reserved"):
            reserve(self.conn, "folder", self.digest, "c" * 32)

    def test_replay_denied(self):
        reserve(self.conn, "folder", self.digest, self.owner)
        with self.assertRaises(UploadReservationDenied):
            reserve(self.conn, "folder", self.digest, self.owner)

    def test_wrong_owner_cannot_complete(self):
        reserve(self.conn, "folder", self.digest, self.owner)
        with self.assertRaises(UploadReservationDenied):
            complete_reservation(self.conn, "folder", self.digest, "c" * 32, "file")

    def test_double_complete_denied(self):
        reserve(self.conn, "folder", self.digest, self.owner)
        complete_reservation(self.conn, "folder", self.digest, self.owner, "file")
        with self.assertRaises(UploadReservationDenied):
            complete_reservation(self.conn, "folder", self.digest, self.owner, "file")

    def test_invalid_digest_denied(self):
        with self.assertRaises(UploadReservationDenied):
            reserve(self.conn, "folder", "INVALID", self.owner)

    def test_invalid_owner_denied(self):
        with self.assertRaises(UploadReservationDenied):
            reserve(self.conn, "folder", self.digest, "owner")

    def test_missing_reservation_denied(self):
        with self.assertRaises(UploadReservationDenied):
            complete_reservation(self.conn, "folder", self.digest, self.owner, "file")

    def test_invalid_file_ids_denied(self):
        reserve(self.conn, "folder", self.digest, self.owner)
        for file_id in ("", "x" * 257, None):
            with self.subTest(file_id=file_id):
                with self.assertRaises(UploadReservationDenied):
                    complete_reservation(self.conn, "folder", self.digest, self.owner, file_id)

    def test_invalid_parent_ids_denied(self):
        for parent in ("", "x" * 257, None):
            with self.subTest(parent=parent):
                with self.assertRaises(UploadReservationDenied):
                    reserve(self.conn, parent, self.digest, self.owner)
