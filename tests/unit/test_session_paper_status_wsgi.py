import tempfile
import unittest

from alpha_lab.research.oidc_durable_store import DurableOIDCStore
from alpha_lab.research.session_paper_status_wsgi import SessionPaperStatusWSGI


class FakeAccounts:
    def status(self, principal, account):
        if account != "primary" or principal.subject != "owner":
            raise PermissionError("not owner")
        return {"mode": "HALT"}


class SessionPaperIsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = [1000]
        self.sessions = DurableOIDCStore(self.tmp.name + "/sessions.sqlite", now=lambda: self.clock[0])
        self.app = SessionPaperStatusWSGI(sessions=self.sessions, accounts=FakeAccounts())

    def tearDown(self):
        self.sessions.close()
        self.tmp.cleanup()

    def request(self, sid="", *, method="GET", path="/api/research/paper/session-status",
                query="", scheme="https", extra=None):
        result = {}
        env = {"PATH_INFO": path, "REQUEST_METHOD": method, "QUERY_STRING": query,
               "wsgi.url_scheme": scheme, "HTTP_COOKIE": "__Host-alpha_session=" + sid}
        env.update(extra or {})
        def start(status, headers):
            result["status"] = status
        result["body"] = b"".join(self.app(env, start))
        return result["status"], result["body"]

    def test_owner_and_other_account_isolation(self):
        owner = self.sessions.create("owner", "issuer", ttl=30)
        other = self.sessions.create("other", "issuer", ttl=30)
        self.assertTrue(self.request(owner)[0].startswith("200"))
        self.assertTrue(self.request(other)[0].startswith("404"))
        self.assertTrue(self.request(owner, query="account=other")[0].startswith("400"))
        self.assertTrue(self.request(owner, extra={"HTTP_X_ACCOUNT_ID": "other"})[0].startswith("200"))

    def test_expired_revoked_and_forged_session(self):
        owner = self.sessions.create("owner", "issuer", ttl=30)
        self.assertTrue(self.request("forged" * 10)[0].startswith("401"))
        self.sessions.revoke(owner)
        self.assertTrue(self.request(owner)[0].startswith("401"))
        expiring = self.sessions.create("owner", "issuer", ttl=30)
        self.clock[0] = 1030
        self.assertTrue(self.request(expiring)[0].startswith("401"))

    def test_http_and_write_fail_closed(self):
        owner = self.sessions.create("owner", "issuer")
        self.assertTrue(self.request(owner, scheme="http")[0].startswith("403"))
        self.assertTrue(self.request(owner, method="POST")[0].startswith("405"))
        self.assertTrue(self.request(owner, path="/api/orders")[0].startswith("404"))


if __name__ == "__main__":
    unittest.main()
