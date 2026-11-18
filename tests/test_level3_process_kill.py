"""Real child-process termination after nonce claim must fail closed."""
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from tools.level3_staging.signed_create import _database, canonical, apply

class ProcessKillRecoveryTests(unittest.TestCase):
    def test_hard_exit_after_claim_blocks_replay(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"workspace"
            (root/"docs"/"level3-staging").mkdir(parents=True)
            db=Path(d)/"ledger.db"
            key=Ed25519PrivateKey.generate()
            pub=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
            path="docs/level3-staging/terminated.md"
            content="test"
            approval={"operation":"create","path":path,"sha256":hashlib.sha256(content.encode()).hexdigest(),
                      "nonce":"d"*64,"expires_at":1100}
            sig=base64.b64encode(key.sign(canonical(approval))).decode()
            args=[str(root),str(db),base64.b64encode(pub).decode(),json.dumps(approval),sig,path,content]
            code="""import base64,json,os,sys
import tools.level3_staging.signed_create as sc
sc._parent=lambda *a: os._exit(91)
a=sys.argv[1:]
sc.apply(a[0],a[1],base64.b64decode(a[2]),json.loads(a[3]),a[4],a[5],a[6],now=1000)
"""
            proc=subprocess.run([sys.executable,"-c",code,*args],check=False,timeout=15,
                                capture_output=True,text=True)
            self.assertEqual(proc.returncode,91,proc.stderr)
            con=_database(db)
            self.assertEqual(con.execute("SELECT state FROM claims").fetchone()[0],"claimed")
            self.assertEqual(con.execute("SELECT phase FROM audit_outbox").fetchone()[0],"claimed")
            con.close()
            self.assertFalse((root/path).exists())
            with self.assertRaises(Exception):
                apply(root,db,pub,approval,sig,path,content,now=1000)

if __name__=="__main__":
    unittest.main()
