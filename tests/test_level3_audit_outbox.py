"""Transactional audit intent survives journal failure and restart."""
import base64
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from tools.level3_staging.signed_create import apply, canonical, _database

class AuditOutboxTests(unittest.TestCase):
    def test_claim_audit_intent_survives_append_failure(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"workspace"
            (root/"docs"/"level3-staging").mkdir(parents=True)
            db=Path(d)/"ledger.db"
            audit=Path(d)/"audit.jsonl"
            key=Ed25519PrivateKey.generate()
            pub=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
            path="docs/level3-staging/one.md"
            content="hello"
            nonce="b"*64
            approval={"operation":"create","path":path,"sha256":hashlib.sha256(content.encode()).hexdigest(),
                      "nonce":nonce,"expires_at":1100}
            sig=base64.b64encode(key.sign(canonical(approval))).decode()
            with patch.dict(os.environ,{"LEVEL3_AUDIT_PATH":str(audit)}), patch(
                "tools.level3_staging.audit_chain.append",side_effect=OSError("journal unavailable")):
                with self.assertRaises(OSError):
                    apply(root,db,pub,approval,sig,path,content,now=1000)
            con=_database(db)
            self.assertEqual(con.execute("SELECT state FROM claims WHERE nonce=?",(nonce,)).fetchone()[0],"claimed")
            self.assertEqual(con.execute("SELECT phase FROM audit_outbox WHERE nonce=?",(nonce,)).fetchone()[0],"claimed")
            con.close()
            self.assertFalse((root/path).exists())
            with self.assertRaises(Exception):
                apply(root,db,pub,approval,sig,path,content,now=1000)

if __name__=="__main__":
    unittest.main()
