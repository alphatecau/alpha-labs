"""Offline custody unit tests; no database credentials or network required."""
import unittest
import uuid
from tools.level3_staging.postgres_custody import CustodyDenied,claim,complete,pending,receipt_digest,append_audit,verify_audit_chain

class Tx:
    def __init__(self,db):
        self.db=db
    def __enter__(self):
        self.db.events.append("BEGIN")
    def __exit__(self,kind,value,tb):
        self.db.events.append("ROLLBACK" if kind else "COMMIT")
        return False

class Result:
    def __init__(self,row):
        self.row=row
    def fetchone(self):
        return self.row
    def fetchall(self):
        return self.row

class DB:
    def __init__(self):
        self.events=[]
        self.update_row=("a"*64,)
        self.audit_rows=[]
    def transaction(self):
        return Tx(self)
    def execute(self,sql,params=None):
        self.events.append((sql,params))
        if sql.startswith("SELECT sequence,event_id"):
            return Result(self.audit_rows)
        if sql.startswith("SELECT event_hash"):
            return Result(None)
        if sql.startswith("UPDATE"):
            return Result(self.update_row)
        if sql.startswith("SELECT"):
            return Result([("a"*64,"docs/level3-staging/ok.md","b"*64)])
        return Result(None)

class CustodyTests(unittest.TestCase):
    def setUp(self):
        self.db=DB()
        self.args=("a"*64,"b"*64,"docs/level3-staging/ok.md","c"*64)
    def test_atomic_claim(self):
        self.assertEqual(claim(self.db,*self.args)["state"],"claimed")
        self.assertEqual(self.db.events[0],"BEGIN")
        self.assertEqual(self.db.events[-1],"COMMIT")
        self.assertEqual(len([e for e in self.db.events if isinstance(e,tuple)]),2)
    def test_complete_requires_claim(self):
        self.db.update_row=None
        with self.assertRaises(CustodyDenied):
            complete(self.db,self.args[1],self.args[2],self.args[3])
        self.assertEqual(self.db.events[-1],"ROLLBACK")
    def test_reject_path_without_db_access(self):
        with self.assertRaises(CustodyDenied):
            claim(self.db,"a"*64,"b"*64,"../escape","c"*64)
        self.assertFalse(self.db.events)
    def test_pending_never_mutates(self):
        self.assertEqual(len(pending(self.db)),1)
        self.assertTrue(self.db.events[0][0].startswith("SELECT"))
    def test_audit_chain_append_is_serialised(self):
        receipt=append_audit(self.db,str(uuid.uuid4()),"a"*64,"claimed","b"*64)
        self.assertEqual(receipt["previous_hash"],"0"*64)
        self.assertEqual(self.db.events[0],"BEGIN")
        self.assertEqual(self.db.events[-1],"COMMIT")
        self.assertIn("pg_advisory_xact_lock",self.db.events[1][0])
    def test_verify_audit_chain_empty(self):
        self.assertEqual(verify_audit_chain(self.db),{"count":0,"head_hash":"0"*64})
    def test_verify_audit_chain_tamper_denied(self):
        self.db.audit_rows=[(1,str(uuid.uuid4()),"a"*64,"claimed","b"*64,"0"*64,"f"*64)]
        with self.assertRaises(CustodyDenied):
            verify_audit_chain(self.db)
    def test_verify_audit_chain_valid(self):
        event_id=str(uuid.uuid4())
        record={"event_id":event_id,"nonce":"a"*64,"phase":"claimed",
                "payload_sha256":"b"*64,"previous_hash":"0"*64}
        digest=receipt_digest(record)
        self.db.audit_rows=[(1,event_id,"a"*64,"claimed","b"*64,"0"*64,digest)]
        self.assertEqual(verify_audit_chain(self.db)["head_hash"],digest)
    def test_receipt_digest_deterministic(self):
        self.assertEqual(receipt_digest({"a":1,"b":2}),receipt_digest({"b":2,"a":1}))

if __name__=="__main__":
    unittest.main()
