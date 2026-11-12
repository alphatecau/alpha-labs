import json
import tempfile
import unittest
from datetime import datetime, timezone

from alpha_lab.research.paper_account_service import PaperAccountService, VerifiedPrincipal
from alpha_lab.research.paper_identity import PaperIdentityVerifier, issue_test_token
from alpha_lab.research.paper_status_wsgi import PaperStatusWSGI


class PaperStatusWSGITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.accounts = PaperAccountService(self.directory.name)
        self.accounts.open_account(VerifiedPrincipal("alice", "trusted"), "primary")
        self.key = b"test-secret-not-for-production-1234"
        self.now = datetime.fromtimestamp(2000000000, tz=timezone.utc)
        self.app = PaperStatusWSGI(
            verifier=PaperIdentityVerifier(key=self.key, issuer="trusted", audience="paper"),
            accounts=self.accounts, now=lambda: self.now)
        self.token = issue_test_token(self.key, dict(sub="alice", iss="trusted",
                            aud="paper", iat=1999999900, exp=2000000100))

    def tearDown(self):
        self.accounts.close()
        self.directory.cleanup()

    def request(self, method="GET", token=None, path="/api/research/paper/status", query=""):
        state = {}
        def start(status, headers):
            state["status"] = status
            state["headers"] = dict(headers)
        environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query}
        if token is not None:
            environ["HTTP_AUTHORIZATION"] = "Bearer " + token
        body = b"".join(self.app(environ, start))
        return state["status"], json.loads(body), state["headers"]

    def test_authorised_read_only_status(self):
        status, payload, headers = self.request(token=self.token)
        self.assertEqual(status, "200 OK")
        self.assertTrue(payload["paper"]["halted"])
        self.assertFalse(payload["real_money"])
        self.assertEqual(payload["live_copy"], "DISABLED_NOT_IMPLEMENTED")
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_reject_unauthenticated_forged_and_write_requests(self):
        self.assertEqual(self.request()[0], "401 Unauthorized")
        self.assertEqual(self.request(token=self.token + "x")[0], "401 Unauthorized")
        self.assertEqual(self.request(token=self.token, method="POST")[0], "405 Method Not Allowed")
        self.assertEqual(self.request(token=self.token, query="account=bob")[0], "400 Bad Request")
        self.assertEqual(self.request(token=self.token, path="/api/research/paper/execute")[0],
                         "404 Not Found")
        bob = issue_test_token(self.key, dict(sub="bob", iss="trusted", aud="paper",
                                               iat=1999999900, exp=2000000100))
        self.assertEqual(self.request(token=bob)[0], "404 Not Found")


if __name__ == "__main__":
    unittest.main()
