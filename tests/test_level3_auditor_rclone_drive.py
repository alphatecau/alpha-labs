import json
import subprocess
import unittest

from tools.level3_staging.auditor_rclone_drive import RcloneAuditorDrive, RcloneDriveDenied


class FakeRunner:
    def __init__(self):
        self.files = {}
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        action = command[1]
        target = command[2]
        if action == "mkdir":
            return subprocess.CompletedProcess(command, 0, b"", b"")
        if action == "lsjson":
            prefix = target.rstrip("/") + "/"
            listing = [{"Name": name[len(prefix):]} for name in self.files
                       if name.startswith(prefix)]
            return subprocess.CompletedProcess(command, 0, json.dumps(listing).encode(), b"")
        if action == "rcat":
            self.files[target] = kwargs["input"]
            return subprocess.CompletedProcess(command, 0, b"", b"")
        if action == "cat":
            if target not in self.files:
                return subprocess.CompletedProcess(command, 1, b"", b"missing")
            return subprocess.CompletedProcess(command, 0, self.files[target], b"")
        raise AssertionError(action)


class RcloneDriveTests(unittest.TestCase):
    def setUp(self):
        self.runner = FakeRunner()
        self.drive = RcloneAuditorDrive("auditor", "118pwq_VOAGeeS1NOTXmoA4ZVEx4AcMo6",
                                       runner=self.runner)
        self.key = ("level3-checkpoints/alpha-labs-level3_staging/"
                    + "0" * 20 + "-" + "a" * 64 + ".json")

    def test_upload_readback_and_duplicate_denial(self):
        self.assertEqual(self.drive.create_once(self.key, b"signed"), self.key)
        self.assertEqual(self.drive.read(self.key), b"signed")
        with self.assertRaises(RcloneDriveDenied):
            self.drive.create_once(self.key, b"rewrite")
        self.assertEqual(self.drive.read(self.key), b"signed")
        self.assertTrue(all("--drive-root-folder-id" in x for x in self.runner.calls))

    def test_invalid_path_denied(self):
        with self.assertRaises(RcloneDriveDenied):
            self.drive.create_once("../secrets", b"x")

    def test_readback_failure_denied(self):
        with self.assertRaises(RcloneDriveDenied):
            self.drive.read(self.key)


if __name__ == "__main__":
    unittest.main()
