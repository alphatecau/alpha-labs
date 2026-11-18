"""Ephemeral PostgreSQL integration test. Never connects to Neon or production."""
import os
import unittest
import uuid
import hashlib

from tools.level3_staging.postgres_custody import (
    claim, complete, pending, append_audit, verify_audit_chain, CustodyDenied,\n    claim_with_audit, complete_with_audit,
)

@unittest.skipUnless(os.environ.get("LEVEL3_TEST_POSTGRES_DSN"), "isolated test DSN required")
class PostgreSQLCustodyIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        cls.conn = psycopg.connect(os.environ["LEVEL3_TEST_POSTGRES_DSN"], autocommit=True)
        # Test database must be disposable; never run schema changes on an external DB.
        db = cls.conn.execute("SELECT current_database()").fetchone()[0]
        if db != "level3_ci_test":
            raise RuntimeError("refusing to mutate non-ephemeral database")
        from pathlib import Path
        migration=Path("deployment/level3_custody_schema.sql").read_text()
        cls.conn.execute(migration)
        cls.conn.execute("CREATE ROLE level3_ci_broker NOLOGIN")
        cls.conn.execute("CREATE ROLE level3_ci_auditor NOLOGIN")
        cls.conn.execute("GRANT USAGE ON SCHEMA level3_custody TO level3_ci_broker,level3_ci_auditor")
        cls.conn.execute("GRANT SELECT,INSERT ON level3_custody.remote_nonce TO level3_ci_broker")
        cls.conn.execute("GRANT SELECT,INSERT,UPDATE ON level3_custody.approval_claim TO level3_ci_broker")
        cls.conn.execute("GRANT SELECT,INSERT ON level3_custody.audit_event TO level3_ci_broker")
        cls.conn.execute("GRANT USAGE ON SEQUENCE level3_custody.audit_event_sequence_seq TO level3_ci_broker")
        cls.conn.execute("GRANT SELECT ON ALL TABLES IN SCHEMA level3_custody TO level3_ci_auditor")

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_effective_role_grants(self):
        checks=[
            ("level3_ci_broker","INSERT",True),
            ("level3_ci_broker","UPDATE",False),
            ("level3_ci_broker","DELETE",False),
            ("level3_ci_broker","TRUNCATE",False),
            ("level3_ci_auditor","SELECT",True),
            ("level3_ci_auditor","INSERT",False),
            ("level3_ci_auditor","UPDATE",False),
            ("level3_ci_auditor","DELETE",False),
            ("level3_ci_auditor","TRUNCATE",False),
        ]
        for role,privilege,expected in checks:
            with self.subTest(role=role,privilege=privilege):
                actual=self.conn.execute(
                    "SELECT has_table_privilege(%s,'level3_custody.audit_event',%s)",
                    (role,privilege)).fetchone()[0]
                self.assertEqual(actual,expected)

    def test_claim_replay_completion_and_audit(self):
        nonce=hashlib.sha256(uuid.uuid4().bytes).hexdigest()
        remote=hashlib.sha256(uuid.uuid4().bytes).hexdigest()
        path="docs/level3-staging/integration.md"
        digest="a"*64
        self.assertEqual(claim(self.conn,remote,nonce,path,digest)["state"],"claimed")
        with self.assertRaises(Exception):
            claim(self.conn,remote,nonce,path,digest)
        self.assertTrue(any(item["nonce"]==nonce for item in pending(self.conn)))
        self.assertEqual(complete(self.conn,nonce,path,digest)["state"],"complete")
        with self.assertRaises(CustodyDenied):
            complete(self.conn,nonce,path,digest)
        append_audit(self.conn,str(uuid.uuid4()),nonce,"complete",digest)
        self.assertGreaterEqual(verify_audit_chain(self.conn)["count"],1)

    def test_audited_claim_and_completion_atomic(self):
        nonce=hashlib.sha256(uuid.uuid4().bytes).hexdigest()
        remote=hashlib.sha256(uuid.uuid4().bytes).hexdigest()
        path="docs/level3-staging/audited.md"
        digest="d"*64
        before=verify_audit_chain(self.conn)["count"]
        claimed=claim_with_audit(self.conn,remote,nonce,path,digest,str(uuid.uuid4()))
        self.assertEqual(claimed["state"],"claimed")
        finished=complete_with_audit(self.conn,nonce,path,digest,str(uuid.uuid4()))
        self.assertEqual(finished["state"],"complete")
        self.assertEqual(verify_audit_chain(self.conn)["count"],before+2)
        with self.assertRaises(Exception):
            complete_with_audit(self.conn,nonce,path,digest,str(uuid.uuid4()))
        self.assertEqual(verify_audit_chain(self.conn)["count"],before+2)

    def test_atomic_claim_rollback_on_approval_conflict(self):
        nonce=hashlib.sha256(uuid.uuid4().bytes).hexdigest()
        remote1=hashlib.sha256(uuid.uuid4().bytes).hexdigest()
        remote2=hashlib.sha256(uuid.uuid4().bytes).hexdigest()
        path="tests/level3-staging/integration.txt"
        digest="b"*64
        claim(self.conn,remote1,nonce,path,digest)
        with self.assertRaises(Exception):
            claim(self.conn,remote2,nonce,path,digest)
        row=self.conn.execute(
            "SELECT count(*) FROM level3_custody.remote_nonce WHERE nonce=%s",(remote2,)
        ).fetchone()
        self.assertEqual(row[0],0)

if __name__=="__main__":
    unittest.main()
