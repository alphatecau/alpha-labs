"""Opt-in PostgreSQL integration tests against a disposable, explicitly provided database.

Run only with ALPHA_LABS_TEST_POSTGRES_DSN and psycopg installed. Never use production DSNs.
"""
import os
import threading
import unittest
import uuid
from alpha_lab.research.phase3_integrity import POSTGRES_RUNS_DDL, register_postgres_run

DSN=os.environ.get("ALPHA_LABS_TEST_POSTGRES_DSN")
try:
    import psycopg
except ImportError:
    psycopg=None

@unittest.skipUnless(DSN and psycopg, "requires disposable ALPHA_LABS_TEST_POSTGRES_DSN and psycopg")
class IsolatedPostgresRunRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # A dedicated test schema avoids changing shared application tables.
        cls.schema="alpha_test_"+uuid.uuid4().hex[:16]
        with psycopg.connect(DSN, autocommit=True) as conn:
            conn.execute('CREATE SCHEMA "'+cls.schema+'"')
            conn.execute('SET search_path TO "'+cls.schema+'"')
            conn.execute(POSTGRES_RUNS_DDL)

    @classmethod
    def tearDownClass(cls):
        with psycopg.connect(DSN, autocommit=True) as conn:
            conn.execute('DROP SCHEMA IF EXISTS "'+cls.schema+'" CASCADE')

    def connection(self):
        conn=psycopg.connect(DSN)
        conn.execute('SET search_path TO "'+self.schema+'"')
        return conn

    def test_duplicate_persists_across_connections(self):
        owner="owner-"+uuid.uuid4().hex
        with self.connection() as conn:
            with conn.cursor() as cur:
                register_postgres_run(cur,owner,"same-id","a"*64)
        with self.assertRaises(psycopg.errors.UniqueViolation):
            with self.connection() as conn:
                with conn.cursor() as cur:
                    register_postgres_run(cur,owner,"same-id","a"*64)
        with self.connection() as conn:
            with conn.cursor() as cur:
                register_postgres_run(cur,owner+"-other","same-id","a"*64)

    def test_concurrent_duplicate_one_winner(self):
        owner="owner-"+uuid.uuid4().hex
        barrier=threading.Barrier(2)
        results=[]
        lock=threading.Lock()
        def attempt():
            try:
                with self.connection() as conn:
                    barrier.wait(timeout=10)
                    with conn.cursor() as cur:
                        register_postgres_run(cur,owner,"concurrent-id","b"*64)
                outcome="inserted"
            except psycopg.errors.UniqueViolation:
                outcome="duplicate"
            except Exception as exc:
                outcome=type(exc).__name__
            with lock: results.append(outcome)
        threads=[threading.Thread(target=attempt) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=20)
        self.assertEqual(sorted(results),["duplicate","inserted"])
