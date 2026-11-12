import unittest
from alpha_lab.research.oidc_postgres_store import PostgresOIDCStore, SCHEMA


class Cursor:
    def __init__(self, db):
        self.db = db
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        if sql.startswith("INSERT INTO oidc_pending"):
            self.db.pending[params[0]] = params[1:]
        elif sql.startswith("DELETE FROM oidc_pending WHERE state="):
            self.row = self.db.pending.pop(params[0], None)
        elif sql.startswith("INSERT INTO oidc_sessions"):
            self.db.sessions[params[0]] = params[1:]
        elif sql.startswith("SELECT subject,issuer,expires_at"):
            self.row = self.db.sessions.get(params[0])
        elif sql.startswith("DELETE FROM oidc_sessions WHERE sid="):
            self.db.sessions.pop(params[0], None)
        elif sql.startswith("DELETE FROM oidc_pending WHERE expires_at"):
            self.db.pending = {
                k: v for k, v in self.db.pending.items() if v[2] > params[0]
            }
        elif sql.startswith("DELETE FROM oidc_sessions WHERE expires_at"):
            self.db.sessions = {
                k: v for k, v in self.db.sessions.items() if v[2] > params[0]
            }
        else:
            raise AssertionError("Unexpected SQL: " + sql)

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return Cursor(self.db)


class FakeDB:
    def __init__(self):
        self.pending = {}
        self.sessions = {}

    def connect(self):
        return Connection(self)


class PostgresContractTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()
        self.clock = [1000]
        self.a = PostgresOIDCStore(self.db.connect, now=lambda: self.clock[0])
        self.b = PostgresOIDCStore(self.db.connect, now=lambda: self.clock[0])

    def test_shared_state_and_one_time_replay(self):
        state, nonce, verifier = self.a.begin()
        self.assertEqual(self.b.consume(state, nonce), verifier)
        with self.assertRaises(PermissionError):
            self.a.consume(state, nonce)

    def test_wrong_nonce_consumes_state(self):
        state, nonce, _ = self.a.begin()
        with self.assertRaises(PermissionError):
            self.b.consume(state, "x" * 30)
        with self.assertRaises(PermissionError):
            self.a.consume(state, nonce)

    def test_cross_instance_sessions_and_revocation(self):
        alice = self.a.create("alice", "issuer", 30)
        bob = self.a.create("bob", "issuer", 30)
        self.assertEqual(self.b.authenticate(alice)[0], "alice")
        self.assertEqual(self.b.authenticate(bob)[0], "bob")
        self.b.revoke(alice)
        with self.assertRaises(PermissionError):
            self.a.authenticate(alice)
        self.clock[0] = 1030
        with self.assertRaises(PermissionError):
            self.a.authenticate(bob)

    def test_schema_constraints(self):
        self.assertIn("PRIMARY KEY", SCHEMA)
        self.assertIn("expires_at", SCHEMA)


if __name__ == "__main__":
    unittest.main()
