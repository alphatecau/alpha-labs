"""Isolated Level 3 stdio entrypoint smoke tests."""
import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

class StdioTests(unittest.TestCase):
    def test_missing_configuration_fails_closed(self):
        env = os.environ.copy()
        for key in ("LEVEL3_STAGING_ROOT","LEVEL3_LEDGER_PATH","LEVEL3_APPROVER_PUBLIC_KEY_B64"):
            env.pop(key, None)
        proc = subprocess.run([sys.executable,"-m","tools.level3_staging.mcp_signed_stdio"],
                              input="",text=True,capture_output=True,env=env,timeout=10)
        self.assertNotEqual(proc.returncode,0)
        self.assertEqual(proc.stdout,"")

    def test_unsigned_startup_denied(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"workspace"
            root.mkdir()
            env=os.environ.copy()
            env.update(LEVEL3_STAGING_ROOT=str(root),LEVEL3_LEDGER_PATH=str(Path(d)/"ledger.db"),
                       LEVEL3_APPROVER_PUBLIC_KEY_B64=base64.b64encode(b"x"*32).decode())
            request={"jsonrpc":"2.0","id":1,"method":"tools/list"}
            proc=subprocess.run([sys.executable,"-m","tools.level3_staging.mcp_signed_stdio"],
                                input=json.dumps(request)+"\n",text=True,capture_output=True,env=env,timeout=10)
            self.assertNotEqual(proc.returncode,0)
            self.assertEqual(proc.stdout,"")
            self.assertFalse((Path(d)/"ledger.db").exists())

if __name__=="__main__":
    unittest.main()
