"""Broker socket transport smoke tests (not independent-UID acceptance)."""
import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from tools.level3_staging.broker import request
from tools.level3_staging.signed_create import Denied

class BrokerTransportTests(unittest.TestCase):
    def test_roundtrip_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/"broker.sock")
            ready=threading.Event()
            errors=[]
            def server():
                try:
                    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as listener:
                        listener.bind(path)
                        listener.listen(1)
                        ready.set()
                        conn,_=listener.accept()
                        with conn:
                            data=b""
                            while not data.endswith(b"\n"):
                                data+=conn.recv(4096)
                            payload=json.loads(data)
                            self.assertEqual(payload["path"],"docs/level3-staging/a.md")
                            conn.sendall(json.dumps({"ok":True,"receipt":{"status":"complete"}}).encode()+b"\n")
                except Exception as exc:
                    errors.append(exc)
                    ready.set()
            thread=threading.Thread(target=server,daemon=True)
            thread.start()
            self.assertTrue(ready.wait(3))
            args={"path":"docs/level3-staging/a.md","content":"x","approval":{},"signature":"x"}
            self.assertEqual(request(path,args)["status"],"complete")
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
            self.assertFalse(errors)

    def test_missing_broker_refused(self):
        with self.assertRaises(OSError):
            request("/missing/level3.sock",{"path":"x","content":"x","approval":{},"signature":"x"})

if __name__=="__main__":
    unittest.main()
