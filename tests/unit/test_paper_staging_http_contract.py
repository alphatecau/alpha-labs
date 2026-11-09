"""End-to-end WSGI contract tests with real staging factory and durable account store."""
import base64
import json
import tempfile
import unittest
from datetime import datetime, timezone

from alpha_lab.research.paper_identity import issue_test_token
from alpha_lab.research.paper_staging_app import build_app
from alpha_lab.research.paper_account_service import VerifiedPrincipal
from alpha_lab.research.paper_ownership import PaperOwnershipRegistry


class StagingHTTPContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.key = b"staging-test-key-not-a-real-secret-0001"
        self.config = {
            "ALPHA_PAPER_SIGNING_KEY_B64": base64.b64encode(self.key).decode(),
            "ALPHA_PAPER_ISSUER": "staging-test",
            "ALPHA_PAPER_AUDIENCE": "alpha-paper-status",
            "ALPHA_PAPER_DATA_DIR": self.tmp.name,
            "ALPHA_PAPER_OWNER_SUBJECT": "owner",
        }
        self.app = build_app(self.config)
        self.now = datetime.fromtimestamp(2000000000, tz=timezone.utc)
        self.app.now = lambda: self.now

    def tearDown(self):
        self.app.accounts.close()
        self.tmp.cleanup()

    def token(self, **overrides):
        claims = {"sub": "owner", "iss": "staging-test", "aud": "alpha-paper-status",
                  "iat": 1999999900, "exp": 2000000100}
        claims.update(overrides)
        return issue_test_token(self.key, claims)

    def call(self, method="GET", token=None, path="/api/research/paper/status",
             query="", extra=None):
        result = {}
        def start(status, headers):
            result["status"] = status
            result["headers"] = dict(headers)
        env = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query}
        if token is not None:
            env["HTTP_AUTHORIZATION"] = "Bearer " + token
        env.update(extra or {})
        result["body"] = json.loads(b"".join(self.app(env, start)))
        return result

    def test_valid_owner_is_read_only_and_halted(self):
        result = self.call(token=self.token())
        self.assertEqual(result["status"], "200 OK")
        self.assertTrue(result["body"]["paper"]["halted"])
        self.assertFalse(result["body"]["real_money"])
        self.assertEqual(result["body"]["live_copy"], "DISABLED_NOT_IMPLEMENTED")
        self.assertEqual(result["headers"]["Cache-Control"], "no-store")

    def test_untrusted_identity_and_write_routes_fail_closed(self):
        self.assertEqual(self.call()["status"], "401 Unauthorized")
        self.assertEqual(self.call(token=self.token(sub="other"))["status"], "404 Not Found")
        self.assertEqual(self.call(token=self.token(aud="wrong"))["status"], "401 Unauthorized")
        self.assertEqual(self.call(token=self.token(exp=2000000000))["status"], "401 Unauthorized")
        self.assertEqual(self.call(token="☃.abc")["status"], "401 Unauthorized")
        self.assertEqual(self.call(token=self.token(), method="POST")["status"],
                         "405 Method Not Allowed")
        self.assertEqual(self.call(token=self.token(), query="subject=other")["status"],
                         "400 Bad Request")
        for path in ("/api/research/paper/execute", "/api/research/paper/enable",
                     "/api/research/live-copy"):
            self.assertEqual(self.call(token=self.token(), path=path)["status"],
                             "404 Not Found")
        # Header spoofing must not alter the principal derived from the token.
        self.assertEqual(self.call(token=self.token(sub="other"),
                         extra={"HTTP_X_USER_ID": "owner"})["status"], "404 Not Found")


    def test_revocation_denies_http_and_survives_restart(self):
        owner = VerifiedPrincipal("owner", "staging-test")
        self.assertEqual(self.call(token=self.token())["status"], "200 OK")
        self.app.accounts.ownership.revoke(owner, "primary")
        self.assertEqual(self.call(token=self.token())["status"], "404 Not Found")
        self.app.accounts.close()
        self.app = build_app(self.config)
        self.app.now = lambda: self.now
        self.assertEqual(self.call(token=self.token())["status"], "404 Not Found")

    def test_account_owner_cannot_be_spoofed_via_request_headers(self):
        outsider = self.token(sub="outsider")
        self.assertEqual(self.call(token=outsider,
                         extra={"HTTP_X_USER_ID": "owner",
                                "HTTP_X_FORWARDED_USER": "owner",
                                "HTTP_X_AUTHENTICATED_SUBJECT": "owner"})["status"],
                         "404 Not Found")


if __name__ == "__main__":
    unittest.main()
