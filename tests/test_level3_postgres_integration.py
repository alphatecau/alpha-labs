"""Ephemeral PostgreSQL integration test. Never connects to Neon or production."""
import os
import unittest
import uuid
import hashlib

from tools.level3_staging.postgres_custody import (
    claim, complete, pending, append_audit, verify_audit_chain, CustodyDenied,
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
        with cls.conn.transaction():
            cls.conn.execute("CREATE SCHEMA level3_custody")
            cls.conn.execute("""CREATE TABLE level3_custody.remote_nonce(
                nonce char(64) PRIMARY KEY, claimed_at timestamptz NOT NULL DEFAULT now())""")
            cls.conn.execute("""CREATE TABLE level3_custody.approval_claim(
                nonce char(64) PRIMARY KEY, path text NOT NULL, payload_sha256 char(64) NOT NULL,
                state text NOT NULL CHECK(state IN ('claimed','complete')),
                created_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz)""")
            cls.conn.execute("""CREATE TABLE level3_custody.audit_event(
                sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                event_id uuid NOT NULL UNIQUE, nonce char(64) NOT NULL, phase text NOT NULL,
                payload_sha256 char(64) NOT NULL, previous_hash char(64) NOT NULL,
                event_hash char(64) NOT NULL UNIQUE, created_at timestamptz NOT NULL DEFAULT now())""")

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

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
