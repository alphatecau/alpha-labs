import os
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
import ed25519_protocol_v5 as protocol
import offline_signer_v5 as signer
import signed_protocol_v4 as v4

class SignerTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"signer.key"
            public = signer.create_key(path)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            key = signer.load_private_key(path)
            envelope = signer.sign_task(key,"operator-1","android-dev-01","repo_status","alpha-labs",1800000000)
            self.assertEqual(protocol.verify(envelope,{"operator-1":Ed25519PublicKey.from_public_bytes(public)},"android-dev-01",1800000000)["repo"],"alpha-labs")
    def test_existing_key_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"key"
            signer.create_key(path)
            original=path.read_bytes()
            with self.assertRaises(FileExistsError): signer.create_key(path)
            self.assertEqual(path.read_bytes(),original)
    def test_private_key_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"key"
            signer.create_key(path)
            path.chmod(0o644)
            with self.assertRaises(ValueError): signer.load_private_key(path)
    def test_symlink_forbidden(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"key";signer.create_key(path)
            link=Path(directory)/"link";link.symlink_to(path)
            with self.assertRaises(ValueError): signer.load_private_key(link)
    def test_shell_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"key";signer.create_key(path)
            with self.assertRaises(ValueError): signer.sign_task(signer.load_private_key(path),"operator-1","android-dev-01","shell","alpha-labs",1800000000)
    def test_unknown_repo_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"key";signer.create_key(path)
            with self.assertRaises(ValueError): signer.sign_task(signer.load_private_key(path),"operator-1","android-dev-01","repo_log","other",1800000000)
    def test_invalid_key_id(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"key";signer.create_key(path)
            with self.assertRaises(ValueError): signer.sign_task(signer.load_private_key(path),"bad/key","android-dev-01","repo_log","alpha-labs",1800000000)

if __name__=="__main__":
    unittest.main()
