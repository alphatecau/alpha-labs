"""Synthetic two-principal tests for the external BFF identity bridge."""
import tempfile
import unittest
from unittest.mock import Mock

from deployment.account_role_research_reader import AccountRoleResearchReader

from alpha_lab.research.oidc_durable_store import DurableOIDCStore
from alpha_lab.research.paper_ownership_registry import PaperOwnershipRegistry
from alpha_lab.research.paper_account_service import VerifiedPrincipal
from alpha_lab.research.identity_rate_limit import SQLiteIdentityLimiter
from deployment.bff_session_bridge import SessionOwnershipVerifier
from deployment.trusted_site_relay import TrustedSiteRelay
from deployment.research_readonly_api import ResearchReadOnlyAPI


class SyntheticReader:
    def list_runs(self, owner, limit):
        return [{"run_id": "run-a" if owner == self.a else "run-b", "owner": owner}]
    def summary(self, owner):
        return {"owner": owner}


class TwoUserBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sessions = DurableOIDCStore(self.tmp.name + "/sessions.sqlite", now=lambda: 1000)
        self.owners = PaperOwnershipRegistry(self.tmp.name + "/owners.sqlite")
        self.limiter = SQLiteIdentityLimiter(self.tmp.name + "/limits.sqlite", limit=20, window=60, clock=__import__("time").time)
        self.verify = SessionOwnershipVerifier(sessions=self.sessions, ownership=self.owners, limiter=self.limiter)
        self.secret = "test-only-secret-" + "x" * 48
        self.reader = SyntheticReader()
        self.api = ResearchReadOnlyAPI(reader=Mock(spec=AccountRoleResearchReader, wraps=self.reader), secret=self.secret)

        def backend(path, headers):
            response = {}
            env = {"PATH_INFO": path, "REQUEST_METHOD": "GET", "HTTP_AUTHORIZATION": headers["Authorization"]}
            body = b"".join(self.api(env, lambda status, hdr: response.update(status=status)))
            import json
            if not response["status"].startswith("200"):
                raise RuntimeError("backend rejected")
            return json.loads(body)

        self.relay = TrustedSiteRelay(self.verify, backend, self.secret)
        self.a = VerifiedPrincipal(subject="alice", issuer="https://issuer.example/")
        self.b = VerifiedPrincipal(subject="bob", issuer="https://issuer.example/")
        self.owners.provision(self.a, "primary")
        self.owners.provision(self.b, "primary")
        self.sid_a = self.sessions.create("alice", self.a.issuer)
        self.sid_b = self.sessions.create("bob", self.b.issuer)
        self.reader.a = self.verify(self.cookie(self.sid_a))["owner_id"]

    @staticmethod
    def cookie(sid):
        return "__Host-alpha_session=" + sid

    def tearDown(self):
        self.sessions.close()
        self.owners.close()
        self.limiter.close()
        self.tmp.cleanup()

    def test_two_users_receive_disjoint_research(self):
        a = self.relay.fetch(self.cookie(self.sid_a), "runs")["data"]
        b = self.relay.fetch(self.cookie(self.sid_b), "runs")["data"]
        self.assertEqual(a[0]["run_id"], "run-a")
        self.assertEqual(b[0]["run_id"], "run-b")
        self.assertNotEqual(a[0]["owner"], b[0]["owner"])

    def test_revoked_owner_denied_before_backend(self):
        self.owners.revoke(self.a, "primary")
        with self.assertRaises(PermissionError):
            self.relay.fetch(self.cookie(self.sid_a), "runs")

    def test_forged_and_missing_cookie_denied(self):
        for cookie in ("", self.cookie("forged" * 10), self.cookie(self.sid_a) + "; account=bob"):
            with self.assertRaises(PermissionError):
                self.relay.fetch(cookie, "runs")

    def test_no_write_routes(self):
        with self.assertRaises(ValueError):
            self.relay.fetch(self.cookie(self.sid_a), "orders")


if __name__ == "__main__":
    unittest.main()
