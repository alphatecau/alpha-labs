import unittest

from tools.level3_staging.drive_custody_upload import upload_and_verify
from tools.level3_staging.drive_readback import CustodyReadbackDenied


class FakeDrive:
    def __init__(self):
        self.objects = []
        self.fail_after_create = False
        self.corrupt_readback = False
        self.create_calls = 0

    def find_by_name(self, parent_id, name):
        return [obj["metadata"] for obj in self.objects
                if obj["metadata"]["parents"] == [parent_id]
                and obj["metadata"]["name"] == name]

    def create(self, parent_id, name, payload):
        self.create_calls += 1
        metadata = {"id": str(self.create_calls), "name": name,
                    "parents": [parent_id], "trashed": False}
        self.objects.append({"metadata": metadata, "payload": payload})
        if self.fail_after_create:
            raise TimeoutError("response lost")
        return metadata

    def download(self, file_id):
        payload = next(obj["payload"] for obj in self.objects
                       if obj["metadata"]["id"] == file_id)
        return payload + b"tampered" if self.corrupt_readback else payload


class DriveUploaderTests(unittest.TestCase):
    def test_upload_readback(self):
        drive = FakeDrive()
        result = upload_and_verify(drive, "folder", b"encrypted-test")
        self.assertEqual(result["file_id"], "1")
        self.assertEqual(drive.create_calls, 1)

    def test_recovery_reuses_existing_object(self):
        drive = FakeDrive()
        upload_and_verify(drive, "folder", b"encrypted-test")
        upload_and_verify(drive, "folder", b"encrypted-test")
        self.assertEqual(drive.create_calls, 1)

    def test_lost_create_response_fails_closed_then_recovers(self):
        drive = FakeDrive()
        drive.fail_after_create = True
        with self.assertRaisesRegex(CustodyReadbackDenied, "ambiguous upload"):
            upload_and_verify(drive, "folder", b"encrypted-test")
        drive.fail_after_create = False
        result = upload_and_verify(drive, "folder", b"encrypted-test")
        self.assertEqual(result["file_id"], "1")
        self.assertEqual(drive.create_calls, 1)

    def test_duplicate_named_objects_denied(self):
        drive = FakeDrive()
        upload_and_verify(drive, "folder", b"encrypted-test")
        drive.objects.append(dict(drive.objects[0]))
        with self.assertRaisesRegex(CustodyReadbackDenied, "ambiguous"):
            upload_and_verify(drive, "folder", b"encrypted-test")

    def test_corrupt_readback_denied(self):
        drive = FakeDrive()
        drive.corrupt_readback = True
        with self.assertRaisesRegex(CustodyReadbackDenied, "digest mismatch"):
            upload_and_verify(drive, "folder", b"encrypted-test")

    def test_bad_parent_denied(self):
        with self.assertRaises(CustodyReadbackDenied):
            upload_and_verify(FakeDrive(), "", b"x")

    def test_bad_payload_denied(self):
        with self.assertRaises(CustodyReadbackDenied):
            upload_and_verify(FakeDrive(), "folder", "plaintext")


if __name__ == "__main__":
    unittest.main()
