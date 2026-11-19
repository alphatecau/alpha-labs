"""Offline staging checks; no real Google Drive/KMS claims."""
import tempfile
import unittest
from pathlib import Path

from tools.level3_staging.auditor_software_key import (
    EncryptedAuditorSigner, AuditorKeyDenied,
)
from tools.level3_staging.auditor_file_store import AuditorFileStore
from tools.level3_staging.auditor_drive_mirror import (
    DriveCheckpointMirror, MirroredAuditorStore, MirrorDenied,
)
from tools.level3_staging.auditor_checkpoint import sign_and_retain


class FakeDrive:
    def __init__(self):
        self.files = {}
        self.corrupt = False

    def create_once(self, name, raw):
        if name in self.files:
            raise FileExistsError(name)
        self.files[name] = raw
        return name

    def read(self, file_id):
        raw = self.files[file_id]
        return raw + b"tampered" if self.corrupt else raw


class AuditorStagingWorkaroundTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name) / "private"
        root.mkdir(mode=0o700)
        self.key_path = root / "auditor.key"
        self.store = AuditorFileStore(root)
        self.drive = FakeDrive()
        self.mirror = MirroredAuditorStore(self.store, DriveCheckpointMirror(self.drive))
        self.password = "auditor-test-passphrase-not-production"
        self.signer = EncryptedAuditorSigner.create(self.key_path, self.password)
        self.receipt = {
            "version": 1, "audience": "alpha-labs-level3:staging",
            "count": 1, "last_sequence": 1, "head_hash": "a" * 64,
        }

    def test_persistent_key_survives_restart(self):
        reopened = EncryptedAuditorSigner.open(self.key_path, self.password)
        self.assertEqual(reopened.public_key, self.signer.public_key)
        self.assertEqual(reopened.sign(b"test"), self.signer.sign(b"test"))

    def test_wrong_passphrase_and_duplicate_creation_denied(self):
        with self.assertRaises(AuditorKeyDenied):
            EncryptedAuditorSigner.open(self.key_path, "incorrect-password-long-enough")
        with self.assertRaises(FileExistsError):
            EncryptedAuditorSigner.create(self.key_path, self.password)

    def test_signed_checkpoint_mirrored_before_head_advance(self):
        result = sign_and_retain(self.receipt, self.signer, self.mirror,
                                 self.signer.public_key)
        self.assertEqual(self.store.read_latest(self.receipt["audience"])["receipt"],
                         self.receipt)
        self.assertEqual(len(self.drive.files), 1)
        self.assertEqual(self.drive.read(result["key"]), self.store.read(result["key"]))

    def test_corrupt_external_readback_blocks_head(self):
        self.drive.corrupt = True
        with self.assertRaises(MirrorDenied):
            sign_and_retain(self.receipt, self.signer, self.mirror,
                            self.signer.public_key)
        self.assertIsNone(self.store.read_latest(self.receipt["audience"]))


if __name__ == "__main__":
    unittest.main()
