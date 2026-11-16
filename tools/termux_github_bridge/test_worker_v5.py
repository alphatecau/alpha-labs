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
            publish.assert_called_once()
        execute.assert_called_once()
    def test_reserved_no_retry(self):
        x=self.issue()
        task=w.validate(x,self.keys,DEVICE,NOW)
        w.reserve(self.db,123,task)
        with patch("worker_v5.worker_v2.execute") as execute:
            with self.assertRaises(v4.Rejected):w.process(x,self.keys,DEVICE,self.db,True,NOW)
            execute.assert_not_called()
    def test_wrong_device(self):
        with self.assertRaises(v4.Rejected):w.process(self.issue(),self.keys,"other-device-01",self.db,True,NOW)

if __name__=="__main__":
    unittest.main()
