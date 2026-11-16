import base64
import json
import sqlite3
import unittest
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import ed25519_protocol_v5 as p
import signed_protocol_v4 as v4
import worker_v5 as w

NOW=1800000000
DEVICE="android-dev-01"
class Tests(unittest.TestCase):
    def setUp(self):
        self.key=Ed25519PrivateKey.generate()
        self.keys={"operator-1":self.key.public_key()}
        self.db=sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE tasks (issue INTEGER PRIMARY KEY, nonce TEXT UNIQUE NOT NULL, operation TEXT NOT NULL, repo TEXT NOT NULL, status TEXT NOT NULL)")
    def tearDown(self):
        self.db.close()
    def issue(self):
        task={"schema":4,"device":DEVICE,"nonce":"a"*32,"issued_at":NOW-5,"expires_at":NOW+120,"operation":"repo_status","repo":"alpha-labs"}
        sig=base64.b64encode(self.key.sign(p.DOMAIN+b"operator-1\x00"+v4.canonical(task))).decode()
        return {"number":123,"author":{"login":"alphatecau"},"labels":[{"name":w.LABEL}],"body":json.dumps({"task":task,"key_id":"operator-1","signature":sig})}
    def test_dry_run(self):
        with patch("worker_v5.worker_v2.execute") as execute:
            self.assertEqual(w.process(self.issue(),self.keys,DEVICE,self.db,now=NOW),"verified-only")
            execute.assert_not_called()
    def test_execute_once(self):
        with patch("worker_v5.worker_v2.execute",return_value="success") as execute, patch("worker_v5.publish"):
            self.assertEqual(w.process(self.issue(),self.keys,DEVICE,self.db,True,NOW),"success")
            with self.assertRaises(v4.Rejected):w.process(self.issue(),self.keys,DEVICE,self.db,True,NOW)
            execute.assert_called_once()
    def test_bad_author(self):
        x=self.issue();x["author"]["login"]="attacker"
        with self.assertRaises(v4.Rejected):w.process(x,self.keys,DEVICE,self.db,True,NOW)
    def test_missing_label(self):
        x=self.issue();x["labels"]=[]
        with self.assertRaises(v4.Rejected):w.process(x,self.keys,DEVICE,self.db,True,NOW)
    def test_tamper(self):
        x=self.issue();b=json.loads(x["body"]);b["task"]["repo"]="Q3HASH";x["body"]=json.dumps(b)
        with self.assertRaises(v4.Rejected):w.process(x,self.keys,DEVICE,self.db,True,NOW)
    def test_receipt_retry_no_execution(self):
        x=self.issue()
        with patch("worker_v5.worker_v2.execute",return_value="success") as execute, patch("worker_v5.publish",side_effect=RuntimeError("offline")):
            with self.assertRaises(RuntimeError):w.process(x,self.keys,DEVICE,self.db,True,NOW)
        with patch("worker_v5.publish") as publish:
            w.reconcile(self.db,[x])
            publish.assert_not_called()
        execute.assert_called_once()
    def test_ambiguous_receipt_never_republished(self):
        x=self.issue()
        with patch("worker_v5.worker_v2.execute",return_value="success"), patch("worker_v5.publish",side_effect=RuntimeError("network failed after comment")) as publish:
            with self.assertRaises(RuntimeError):
                w.process(x,self.keys,DEVICE,self.db,True,NOW)
            w.reconcile(self.db,[x])
            publish.assert_called_once()
        self.assertEqual(self.db.execute("SELECT status FROM tasks WHERE issue=123").fetchone()[0],"publishing_success")
    def test_successful_receipt_marked_published(self):
        x=self.issue()
        with patch("worker_v5.worker_v2.execute",return_value="success"), patch("worker_v5.publish") as publish:
            w.process(x,self.keys,DEVICE,self.db,True,NOW)
            w.reconcile(self.db,[x])
            publish.assert_called_once()
        self.assertEqual(self.db.execute("SELECT status FROM tasks WHERE issue=123").fetchone()[0],"published_success")
    def test_reserved_no_retry(self):
        x=self.issue()
        task=w.validate(x,self.keys,DEVICE,NOW)
        w.reserve(self.db,123,task)
        with patch("worker_v5.worker_v2.execute") as execute:
            with self.assertRaises(v4.Rejected):w.process(x,self.keys,DEVICE,self.db,True,NOW)
            execute.assert_not_called()
    def test_queue_capacity_accepts_bounded_list(self):
        self.assertEqual(w.check_queue_capacity([self.issue()], limit=2), [self.issue()])
    def test_queue_capacity_rejects_truncation(self):
        with self.assertRaises(v4.Rejected):
            w.check_queue_capacity([self.issue(), self.issue()], limit=2)
    def test_queue_capacity_rejects_malformed_response(self):
        with self.assertRaises(v4.Rejected):
            w.check_queue_capacity({"issues": []})
    def test_paginated_queue_multiple_pages(self):
        def raw(number):
            x=self.issue()
            return {"number":number,"user":x["author"],"labels":x["labels"],"body":x["body"]}
        pages=[[raw(123)],[raw(124)]]
        with patch("worker_v5.worker_v2.run",return_value=json.dumps(pages)) as run:
            self.assertEqual([x["number"] for x in w.fetch_issues()], [123,124])
            self.assertIn("--paginate",run.call_args.args[0])
            self.assertIn("--slurp",run.call_args.args[0])
    def test_paginated_queue_rejects_duplicate(self):
        x=self.issue()
        raw={"number":123,"user":x["author"],"labels":x["labels"],"body":x["body"]}
        with patch("worker_v5.worker_v2.run",return_value=json.dumps([[raw],[raw]])):
            with self.assertRaises(v4.Rejected):w.fetch_issues()
    def test_paginated_queue_rejects_malformed_page(self):
        with patch("worker_v5.worker_v2.run",return_value=json.dumps([{}])):
            with self.assertRaises(v4.Rejected):w.fetch_issues()
    def test_paginated_queue_rejects_oversized(self):
        x=self.issue()
        raw={"number":123,"user":x["author"],"labels":x["labels"],"body":x["body"]}
        with patch("worker_v5.worker_v2.run",return_value=json.dumps([[raw]])):
            with self.assertRaises(v4.Rejected):w.fetch_issues(max_issues=0)
    def test_paginated_queue_ignores_pull_requests(self):
        x=self.issue()
        raw={"number":123,"user":x["author"],"labels":x["labels"],"body":x["body"],"pull_request":{}}
        with patch("worker_v5.worker_v2.run",return_value=json.dumps([[raw]])):
            self.assertEqual(w.fetch_issues(), [])
    def test_wrong_device(self):
        with self.assertRaises(v4.Rejected):w.process(self.issue(),self.keys,"other-device-01",self.db,True,NOW)

if __name__=="__main__":
    unittest.main()
