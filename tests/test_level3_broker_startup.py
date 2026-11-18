"""Broker-backed worker must refuse startup without readiness evidence."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

class BrokerStartupTests(unittest.TestCase):
    def test_missing_readiness_denied(self):
        with tempfile.TemporaryDirectory() as d:
            sock_path=Path(d)/"broker.sock"
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as server:
                server.bind(str(sock_path))
                env=os.environ.copy()
                env["LEVEL3_BROKER_SOCKET"]=str(sock_path)
                for key in ("LEVEL3_READINESS_ATTESTATION","LEVEL3_READINESS_PUBLIC_KEY_B64"):
                    env.pop(key,None)
                proc=subprocess.run([sys.executable,"-m","tools.level3_staging.mcp_broker_stdio"],
                    input=json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/list"})+"\n",
                    text=True,capture_output=True,env=env,timeout=10)
                self.assertNotEqual(proc.returncode,0)
                self.assertEqual(proc.stdout,"")

if __name__=="__main__":
    unittest.main()
