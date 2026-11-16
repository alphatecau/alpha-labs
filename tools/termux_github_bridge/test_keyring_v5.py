import base64
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import keyring_v5 as k
import signed_protocol_v4 as v4

class KeyringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/"private"/"keys.json"
        self.raw = Ed25519PrivateKey.generate().public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.encoded = base64.b64encode(self.raw).decode()
        self.fp = k.fingerprint(self.raw)
    def test_enrol(self):
        k.enrol(self.path,"operator-1",self.encoded,self.fp)
        self.assertIn("operator-1",k.trusted_keys(self.path))
        self.assertEqual(self.path.stat().st_mode & 0o777,0o600)
    def test_revoke(self):
        k.enrol(self.path,"operator-1",self.encoded,self.fp)
        k.revoke(self.path,"operator-1")
        self.assertEqual(k.trusted_keys(self.path),{})
    def test_bad_fingerprint(self):
        with self.assertRaises(v4.Rejected):
            k.enrol(self.path,"operator-1",self.encoded,"0"*64)
        self.assertFalse(self.path.exists())
    def test_duplicate_key_id(self):
        k.enrol(self.path,"operator-1",self.encoded,self.fp)
        with self.assertRaises(v4.Rejected):
            k.enrol(self.path,"operator-1",self.encoded,self.fp)
    def test_bad_key(self):
        with self.assertRaises(v4.Rejected):
            k.enrol(self.path,"operator-1",base64.b64encode(b"x").decode(),self.fp)
    def test_symlink(self):
        target=Path(self.temp.name)/"target"
        target.write_text("{}")
        self.path.parent.mkdir()
        self.path.symlink_to(target)
        with self.assertRaises(v4.Rejected):
            k.enrol(self.path,"operator-1",self.encoded,self.fp)
    def test_insecure_directory(self):
        self.path.parent.mkdir(mode=0o777)
        self.path.parent.chmod(0o755)
        with self.assertRaises(v4.Rejected):
            k.enrol(self.path,"operator-1",self.encoded,self.fp)
    def test_insecure_file(self):
        self.path.parent.mkdir(mode=0o700)
        self.path.write_text("{}")
        self.path.chmod(0o644)
        with self.assertRaises(v4.Rejected):
            k.trusted_keys(self.path)

if __name__=="__main__":
    unittest.main()
