import copy
import sqlite3
import unittest
from unittest.mock import patch
import signed_protocol_v4 as protocol
import worker_v4

KEY = b"k" * 32
DEVICE = "termux-device-01"
NOW = 1800000000

def issue():
    task = {"schema": 4, "device": DEVICE, "nonce": "a" * 32,
            "issued_at": NOW - 5, "expires_at": NOW + 120,
            "operation": "repo_status", "repo": "alpha-labs"}
    import json
    return {"number": 777, "author": {"login": "alphatecau"},
            "labels": [{"name": worker_v4.LABEL}],
            "body": json.dumps({"task": task, "signature": protocol.signature_for(task, KEY)})}

class WorkerV4Tests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
    def tearDown(self):
        self.db.close()
    def test_dry_run_no_execute(self):
        with patch("worker_v4.execute_task") as execute:
            self.assertEqual(worker_v4.process(issue(), KEY, DEVICE, self.db, now=NOW), "verified-only")
            execute.assert_not_called()
    def test_execute_once(self):
        with patch("worker_v4.execute_task", return_value="success") as execute, patch("worker_v4.report") as report:
            self.assertEqual(worker_v4.process(issue(), KEY, DEVICE, self.db, True, NOW), "success")
            execute.assert_called_once()
            report.assert_called_once()
            with self.assertRaises(protocol.Rejected):
                worker_v4.process(issue(), KEY, DEVICE, self.db, True, NOW)
    def test_wrong_author(self):
        x=issue(); x["author"]["login"]="attacker"
        with self.assertRaises(protocol.Rejected):
            worker_v4.process(x, KEY, DEVICE, self.db, True, NOW)
    def test_missing_label(self):
        x=issue(); x["labels"]=[]
        with self.assertRaises(protocol.Rejected):
            worker_v4.process(x, KEY, DEVICE, self.db, True, NOW)
    def test_tamper(self):
        import json
        x=issue(); body=json.loads(x["body"]); body["task"]["repo"]="Q3HASH"; x["body"]=json.dumps(body)
        with self.assertRaises(protocol.Rejected):
            worker_v4.process(x, KEY, DEVICE, self.db, True, NOW)
    def test_no_receipt_if_invalid(self):
        with patch("worker_v4.report") as report:
            with self.assertRaises(protocol.Rejected):
                worker_v4.process({**issue(), "author":{"login":"other"}}, KEY, DEVICE, self.db, True, NOW)
            report.assert_not_called()
    def test_failure_receipt(self):
        with patch("worker_v4.execute_task", side_effect=RuntimeError("secret")), patch("worker_v4.report") as report:
            self.assertEqual(worker_v4.process(issue(), KEY, DEVICE, self.db, True, NOW), "failed")
            self.assertEqual(report.call_args.args[2], "failed")
    def test_bad_key_mode(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"key"; p.write_bytes(KEY); p.chmod(0o644)
            with self.assertRaises(RuntimeError): worker_v4.read_key(p)
    def test_good_key_mode(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"key"; p.write_bytes(KEY); p.chmod(0o600)
            self.assertEqual(worker_v4.read_key(p), KEY)

if __name__ == "__main__":
    unittest.main()
