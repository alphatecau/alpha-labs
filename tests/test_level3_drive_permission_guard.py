import unittest

from tools.level3_staging.drive_permission_guard import (
    DrivePermissionDenied,
    verify_auditor_folder,
)


class PermissionGuardTests(unittest.TestCase):
    def setUp(self):
        self.folder = {
            "mimeType": "application/vnd.google-apps.folder",
            "trashed": False,
            "owners": [{"emailAddress": "auditor@example.com"}],
            "permissions": [
                {"type": "user", "role": "owner", "emailAddress": "auditor@example.com"},
                {"type": "user", "role": "reader", "emailAddress": "broker@example.com"},
            ],
        }

    def test_private_folder(self):
        self.assertTrue(verify_auditor_folder(self.folder, "auditor@example.com"))

    def test_public_link_denied(self):
        self.folder["permissions"].append({"type": "anyone", "role": "reader"})
        with self.assertRaises(DrivePermissionDenied):
            verify_auditor_folder(self.folder, "auditor@example.com")

    def test_broker_writer_denied(self):
        self.folder["permissions"][1]["role"] = "writer"
        with self.assertRaises(DrivePermissionDenied):
            verify_auditor_folder(self.folder, "auditor@example.com")

    def test_wrong_owner_denied(self):
        with self.assertRaises(DrivePermissionDenied):
            verify_auditor_folder(self.folder, "other@example.com")

    def test_missing_permissions_denied(self):
        self.folder.pop("permissions")
        with self.assertRaises(DrivePermissionDenied):
            verify_auditor_folder(self.folder, "auditor@example.com")

    def test_nonstring_owner_identity_denied(self):
        self.folder["owners"][0]["emailAddress"] = None
        with self.assertRaises(DrivePermissionDenied):
            verify_auditor_folder(self.folder, "auditor@example.com")

    def test_nonstring_permission_identity_denied(self):
        self.folder["permissions"][0]["emailAddress"] = None
        with self.assertRaises(DrivePermissionDenied):
            verify_auditor_folder(self.folder, "auditor@example.com")

    def test_empty_auditor_identity_denied(self):
        with self.assertRaises(DrivePermissionDenied):
            verify_auditor_folder(self.folder, "")

    def test_missing_reader_identity_denied(self):
        self.folder["permissions"][1].pop("emailAddress")
        with self.assertRaises(DrivePermissionDenied):
            verify_auditor_folder(self.folder, "auditor@example.com")
