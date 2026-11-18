"""Crash-point simulation: consumed nonce must never be replayable."""
import base64
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from tools.level3_staging.signed_create import apply, canonical, _database
from tools.level3_staging.recovery import inspect_claims

class FaultInjectionTests(unittest.TestCase):
    def test_failure_after_claim_survives_restart_and_blocks_replay(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"checkout"
            (root/"docs"/"level3-staging").mkdir(parents=True)
            db=Path(d)/"ledger.db"
            path="docs/level3-staging/interrupt.md"
            content="interruption test"
            key=Ed25519PrivateKey.generate()
            pub=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
            approval={"operation":"create","path":path,"sha256":hashlib.sha256(content.encode()).hexdigest(),
                      "nonce":"f"*64,"expires_at":1100}
            sig=base64.b64encode(key.sign(canonical(approval))).decode()
            with patch("tools.level3_staging.signed_create._parent",side_effect=OSError("simulated crash")):
                with self.assertRaises(OSError):
                    apply(root,db,pub,approval,sig,path,content,now=1000)
            report=inspect_claims(db)
            self.assertTrue(report["blocked"])
            self.assertEqual(report["claims"][0]["state"],"claimed")
            with self.assertRaises(Exception):
                apply(root,db,pub,approval,sig,path,content,now=1000)
            self.assertFalse((root/path).exists())
            con=_database(db)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM claims").fetchone()[0],1)
            con.close()

if __name__=="__main__":
    unittest.main()
