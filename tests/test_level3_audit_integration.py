"""Signed create emits durable claim/complete audit events."""
import base64
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from tools.level3_staging.signed_create import apply,canonical
from tools.level3_staging.audit_chain import verify

class AuditIntegrationTests(unittest.TestCase):
    def test_signed_create_audited_and_replay_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"workspace"
            (root/"docs"/"level3-staging").mkdir(parents=True)
            ledger=Path(d)/"claims.db"
            audit=Path(d)/"audit.jsonl"
            key=Ed25519PrivateKey.generate()
            pub=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
            content="hello"
            import hashlib
            path="docs/level3-staging/example.md"
            approval={"operation":"create","path":path,"sha256":hashlib.sha256(content.encode()).hexdigest(),
                      "nonce":"a"*64,"expires_at":1100}
            sig=base64.b64encode(key.sign(canonical(approval))).decode()
            with patch.dict(os.environ,{"LEVEL3_AUDIT_PATH":str(audit)}):
                receipt=apply(root,ledger,pub,approval,sig,path,content,now=1000)
                self.assertEqual(receipt["status"],"complete")
                self.assertEqual(len(audit.read_text().splitlines()),2)
                self.assertEqual(len(verify(audit)),64)
                with self.assertRaises(Exception):
                    apply(root,ledger,pub,approval,sig,path,content,now=1000)
                self.assertEqual(len(audit.read_text().splitlines()),2)

if __name__=="__main__":
    unittest.main()
