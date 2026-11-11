import unittest
import hashlib

from alpha_lab.research.paper_account_service import VerifiedPrincipal
from alpha_lab.research.postgres_paper_security import PostgresPaperOwnership, PostgresIdentityLimiter, SCHEMA


class FakeConnection:
    def __init__(self, state):
        self.state = state
        self.row = None
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return self
    def execute(self, sql, args):
        self.state["sql"].append(sql)
        if sql.startswith("INSERT INTO paper_ownership"):
            self.state["owners"][args] = True
        elif sql.startswith("UPDATE paper_ownership"):
            self.state["owners"][args] = False
        elif sql.startswith("SELECT active"):
            self.row = (self.state["owners"][args],) if args in self.state["owners"] else None
        elif sql.startswith("INSERT INTO identity_rate_limit"):
            key, bucket = args
            old_bucket, count = self.state["limits"].get(key, (None, 0))
            count = count + 1 if old_bucket == bucket else 1
            self.state["limits"][key] = (bucket, count)
            self.row = (count,)
        else:
            raise AssertionError(sql)
    def fetchone(self): return self.row


class PostgresSecurityContractTests(unittest.TestCase):
    def setUp(self):
        self.state = {"owners": {}, "limits": {}, "sql": []}
        self.connect = lambda: FakeConnection(self.state)
        self.owner = VerifiedPrincipal(subject="owner", issuer="https://issuer.example/")
        self.other = VerifiedPrincipal(subject="other", issuer="https://issuer.example/")

    def test_ownership_isolation_and_revocation(self):
        registry = PostgresPaperOwnership(self.connect)
        with self.assertRaises(PermissionError): registry.require(self.owner, "primary")
        registry.provision(self.owner, "primary")
        self.assertTrue(registry.require(self.owner, "primary"))
        with self.assertRaises(PermissionError): registry.require(self.other, "primary")
        registry.revoke(self.owner, "primary")
        with self.assertRaises(PermissionError): registry.require(self.owner, "primary")

    def test_atomic_upsert_contract_and_limits(self):
        now = [120]
        limiter = PostgresIdentityLimiter(self.connect, limit=2, window=60, clock=lambda: now[0])
        self.assertTrue(limiter.allow(self.owner.issuer, self.owner.subject))
        self.assertTrue(limiter.allow(self.owner.issuer, self.owner.subject))
        with self.assertRaises(PermissionError): limiter.allow(self.owner.issuer, self.owner.subject)
        self.assertTrue(limiter.allow(self.other.issuer, self.other.subject))
        now[0] = 180
        self.assertTrue(limiter.allow(self.owner.issuer, self.owner.subject))
        self.assertTrue(any("ON CONFLICT(identity) DO UPDATE" in sql for sql in self.state["sql"]))

    def test_owner_id_lookup_tracks_current_authorization(self):
        registry = PostgresPaperOwnership(self.connect)
        owner = "oidc_" + hashlib.sha256((self.owner.issuer + "\0" + self.owner.subject).encode()).hexdigest()
        registry.provision(self.owner, "primary")
        self.assertTrue(registry.require_owner_id(owner, "primary"))
        registry.revoke(self.owner, "primary")
        with self.assertRaises(PermissionError):
            registry.require_owner_id(owner, "primary")
        before = len(self.state["sql"])
        for owner_id, account in (("oidc_bad", "primary"), (owner, "../bad")):
            with self.assertRaises(PermissionError):
                registry.require_owner_id(owner_id, account)
        self.assertEqual(len(self.state["sql"]), before)

    def test_schema_and_invalid_inputs(self):
        self.assertIn("PRIMARY KEY(owner_digest, account)", SCHEMA)
        with self.assertRaises(PermissionError):
            PostgresPaperOwnership(self.connect).provision({"sub": "owner"}, "primary")
        with self.assertRaises(ValueError):
            PostgresIdentityLimiter(self.connect, limit=0)


if __name__ == "__main__":
    unittest.main()
