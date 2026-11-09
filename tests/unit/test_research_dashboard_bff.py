"""Synthetic BFF HTTP boundary tests; no network or production services."""
import json
import tempfile
import unittest

from alpha_lab.research.oidc_durable_store import DurableOIDCStore
from alpha_lab.research.paper_ownership_registry import PaperOwnershipRegistry
from alpha_lab.research.paper_account_service import VerifiedPrincipal
from alpha_lab.research.identity_rate_limit import SQLiteIdentityLimiter
from deployment.bff_session_bridge import SessionOwnershipVerifier
from deployment.trusted_site_relay import TrustedSiteRelay
from deployment.research_dashboard_bff import ResearchDashboardBFF
from deployment.research_readonly_api import ResearchReadOnlyAPI


class Reader:
    def list_runs(self, owner, limit):
        return [{"run_id": "run_" + owner[-8:], "owner": owner}]
    def summary(self, owner):
        return {"owner": owner, "performance": {"status": "unavailable"}}


class BFFBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.sessions = DurableOIDCStore(self.temp.name + "/sessions.sqlite")
        self.ownership = PaperOwnershipRegistry(self.temp.name + "/owners.sqlite")
        self.limiter = SQLiteIdentityLimiter(self.temp.name + "/limiter.sqlite", limit=20, window=60)
        verifier = SessionOwnershipVerifier(sessions=self.sessions, ownership=self.ownership, limiter=self.limiter)
        secret = "synthetic-only-" + "z" * 48
        api = ResearchReadOnlyAPI(reader=Reader(), secret=secret)
        def backend(path, headers):
            response = {}
            body = b"".join(api({"PATH_INFO": path, "REQUEST_METHOD": "GET",
                                "HTTP_AUTHORIZATION": headers["Authorization"]},
                               lambda status, hdr: response.update(status=status)))
            if not response["status"].startswith("200"):
                raise RuntimeError("backend failed")
            return json.loads(body)
        self.app = ResearchDashboardBFF(relay=TrustedSiteRelay(verifier, backend, secret))
        self.principals = [
            VerifiedPrincipal(subject="alice", issuer="https://issuer.example/"),
            VerifiedPrincipal(subject="bob", issuer="https://issuer.example/"),
        ]
        self.cookies = []
        for principal in self.principals:
            self.ownership.provision(principal, "primary")
            self.cookies.append("__Host-alpha_session=" + self.sessions.create(principal.subject, principal.issuer))

    def tearDown(self):
        self.sessions.close()
        self.ownership.close()
        self.limiter.close()
        self.temp.cleanup()

    def request(self, cookie="", *, path="/api/research/runs", method="GET", scheme="https", query="", extra=None):
        response = {}
        env = {"PATH_INFO": path, "REQUEST_METHOD": method, "wsgi.url_scheme": scheme,
               "QUERY_STRING": query, "HTTP_COOKIE": cookie}
        env.update(extra or {})
        data = b"".join(self.app(env, lambda status, headers: response.update(status=status, headers=dict(headers))))
        return response["status"], json.loads(data), response["headers"]

    def test_two_user_isolation_and_browser_owner_spoof(self):
        a = self.request(self.cookies[0], extra={"HTTP_X_OWNER_ID": "bob"})[1]["data"]["data"][0]
        b = self.request(self.cookies[1])[1]["data"]["data"][0]
        self.assertNotEqual(a["owner"], b["owner"])
        self.assertNotEqual(a["run_id"], b["run_id"])

    def test_unauthenticated_revoked_and_write_denied(self):
        self.assertTrue(self.request()[0].startswith("401"))
        self.ownership.revoke(self.principals[0], "primary")
        self.assertTrue(self.request(self.cookies[0])[0].startswith("401"))
        self.assertTrue(self.request(self.cookies[1], method="POST")[0].startswith("405"))

    def test_https_query_and_unknown_route_denied(self):
        self.assertTrue(self.request(self.cookies[0], scheme="http")[0].startswith("403"))
        self.assertTrue(self.request(self.cookies[0], query="owner=bob")[0].startswith("400"))
        self.assertTrue(self.request(self.cookies[0], path="/api/orders")[0].startswith("404"))

    def test_no_store_or_browser_tokens(self):
        status, body, headers = self.request(self.cookies[0])
        self.assertTrue(status.startswith("200"))
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("Set-Cookie", headers)
        self.assertNotIn("Authorization", headers)
        self.assertNotIn("secret", json.dumps(body).lower())


if __name__ == "__main__":
    unittest.main()
