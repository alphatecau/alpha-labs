import base64
import copy
import sqlite3
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import ed25519_protocol_v5 as p
import signed_protocol_v4 as v4

NOW=1800000000
DEVICE="termux-device-01"
class Tests(unittest.TestCase):
    def setUp(self):
        self.private=Ed25519PrivateKey.generate()
        self.keys={"signer-1":self.private.public_key()}
        self.db=sqlite3.connect(":memory:")
    def tearDown(self):
        self.db.close()
    def envelope(self):
        task={"schema":4,"device":DEVICE,"nonce":"a"*32,"issued_at":NOW-5,
              "expires_at":NOW+120,"operation":"repo_status","repo":"alpha-labs"}
        sig=self.private.sign(p.DOMAIN+b"signer-1\x00"+v4.canonical(task))
        return {"task":task,"key_id":"signer-1","signature":base64.b64encode(sig).decode()}
    def test_valid(self):
        self.assertEqual(p.verify(self.envelope(),self.keys,DEVICE,NOW)["repo"],"alpha-labs")
    def test_replay(self):
        e=self.envelope()
        p.authorize(e,self.keys,DEVICE,self.db,NOW)
        with self.assertRaises(v4.Rejected): p.authorize(e,self.keys,DEVICE,self.db,NOW)
    def test_wrong_device(self):
        with self.assertRaises(v4.Rejected): p.verify(self.envelope(),self.keys,"other-device-01",NOW)
    def test_expired(self):
        with self.assertRaises(v4.Rejected): p.verify(self.envelope(),self.keys,DEVICE,NOW+121)
    def test_tamper(self):
        e=self.envelope();e["task"]["repo"]="Q3HASH"
        with self.assertRaises(v4.Rejected): p.verify(e,self.keys,DEVICE,NOW)
    def test_unknown_key(self):
        with self.assertRaises(v4.Rejected): p.verify(self.envelope(),{},DEVICE,NOW)
    def test_invalid_base64(self):
        e=self.envelope();e["signature"]="***"
        with self.assertRaises(v4.Rejected): p.verify(e,self.keys,DEVICE,NOW)
    def test_shell_denied_even_signed(self):
        e=self.envelope();e["task"]["operation"]="shell"
        e["signature"]=base64.b64encode(self.private.sign(p.DOMAIN+b"signer-1\x00"+v4.canonical(e["task"]))).decode()
        with self.assertRaises(v4.Rejected): p.verify(e,self.keys,DEVICE,NOW)
    def test_extra_field(self):
        e=self.envelope();e["task"]["command"]="whoami"
        with self.assertRaises(v4.Rejected): p.verify(e,self.keys,DEVICE,NOW)
    def test_key_id_change(self):
        e=self.envelope();e["key_id"]="signer-2"
        with self.assertRaises(v4.Rejected): p.verify(e,self.keys,DEVICE,NOW)
    def test_public_key_symlink_rejected(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as root:
            target=Path(root)/"target";target.write_bytes(b"a"*32)
            link=Path(root)/"link";link.symlink_to(target)
            with self.assertRaises(v4.Rejected): p.read_public_key(link)

if __name__=="__main__":
    unittest.main()
