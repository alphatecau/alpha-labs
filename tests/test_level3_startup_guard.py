"""Signed readiness startup verification and fail-closed tests."""
import base64
import json
import tempfile
import unittest
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from tools.level3_staging.startup_guard import verify_startup
from tools.level3_staging.signed_create import canonical
from tools.level3_staging.readiness import Gate

class StartupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"checkout"
        self.root.mkdir()
        self.ledger=Path(self.tmp.name)/"private"/"claims.db"
        self.key=Ed25519PrivateKey.generate()
        from cryptography.hazmat.primitives import serialization
        self.public=self.key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw)
        self.file=Path(self.tmp.name)/"attestation.json"
        self.evidence={"schema":1,"root":str(self.root),"ledger":str(self.ledger),
                       "expires_at":1100,**{k:True for k in vars(Gate())}}

    def save(self):
        signature=base64.b64encode(self.key.sign(canonical(self.evidence))).decode()
        self.file.write_text(json.dumps({"evidence":self.evidence,"signature":signature}))

    def check(self):
        return verify_startup(str(self.file),self.public,self.root,self.ledger,now=1000)

    def test_missing_denied(self):
        with self.assertRaises(SystemExit):
            verify_startup(None,self.public,self.root,self.ledger,now=1000)

    def test_valid_signed_evidence(self):
        self.save()
        self.assertTrue(self.check())

    def test_false_gate_denied(self):
        self.evidence["protected_ledger"]=False
        self.save()
        with self.assertRaises(SystemExit):
            self.check()

    def test_tampered_evidence_denied(self):
        self.save()
        record=json.loads(self.file.read_text())
        record["evidence"]["root"]="/tmp/other"
        self.file.write_text(json.dumps(record))
        with self.assertRaises(SystemExit):
            self.check()

    def test_expired_denied(self):
        self.evidence["expires_at"]=999
        self.save()
        with self.assertRaises(SystemExit):
            self.check()

    def test_wrong_ledger_denied(self):
        self.save()
        with self.assertRaises(SystemExit):
            verify_startup(str(self.file),self.public,self.root,self.root/"ledger.db",now=1000)

if __name__=="__main__":
    unittest.main()
