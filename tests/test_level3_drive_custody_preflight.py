import unittest

from tools.level3_staging.drive_custody_preflight import verify_independent_custody

AUDITOR = "auditor@example.com"
PRIMARY = "primary@example.com"
FOLDER = "folder-id"


def folder():
    return {
        "id": FOLDER, "mimeType": "application/vnd.google-apps.folder",
        "trashed": False, "owners": [{"emailAddress": AUDITOR}],
        "permissions": [
            {"type": "user", "role": "owner", "emailAddress": AUDITOR},
            {"type": "user", "role": "reader", "emailAddress": PRIMARY},
        ],
    }


class CustodyPreflightTests(unittest.TestCase):
    def test_minimal_separation(self):
        self.assertTrue(verify_independent_custody(folder(), AUDITOR, PRIMARY, FOLDER))

    def test_wrong_folder(self):
        with self.assertRaises(ValueError):
            verify_independent_custody(folder(), AUDITOR, PRIMARY, "other")

    def test_auditor_reader_denied(self):
        data = folder()
        data["permissions"][0]["role"] = "reader"
        with self.assertRaisesRegex(ValueError, "explicit owner"):
            verify_independent_custody(data, AUDITOR, PRIMARY, FOLDER)

    def test_primary_writer_denied(self):
        data = folder()
        data["permissions"][1]["role"] = "writer"
        with self.assertRaises(ValueError):
            verify_independent_custody(data, AUDITOR, PRIMARY, FOLDER)

    def test_public_or_third_party_denied(self):
        data = folder()
        data["permissions"].append({"type": "anyone", "role": "reader"})
        with self.assertRaises(ValueError):
            verify_independent_custody(data, AUDITOR, PRIMARY, FOLDER)

    def test_duplicate_reader_principal_denied(self):
        data = folder()
        data["permissions"].append({
            "type": "user", "role": "reader", "emailAddress": PRIMARY,
        })
        with self.assertRaisesRegex(ValueError, "duplicate permission"):
            verify_independent_custody(data, AUDITOR, PRIMARY, FOLDER)

    def test_empty_permission_identity_denied(self):
        data = folder()
        data["permissions"][1]["emailAddress"] = ""
        with self.assertRaises(ValueError):
            verify_independent_custody(data, AUDITOR, PRIMARY, FOLDER)

    def test_same_account_denied(self):
        with self.assertRaises(ValueError):
            verify_independent_custody(folder(), AUDITOR, AUDITOR, FOLDER)

    def test_missing_permission_denied(self):
        data = folder()
        data["permissions"].pop()
        with self.assertRaises(ValueError):
            verify_independent_custody(data, AUDITOR, PRIMARY, FOLDER)
