"""Fail-closed staging WSGI adversarial tests; synthetic identity and data only."""
import unittest
from unittest.mock import Mock

from alpha_lab.research.postgres_paper_security import PostgresIdentityLimiter
from deployment.account_role_research_reader import AccountRoleResearchReader
from deployment.staging_authenticated_bff import StagingResearchBFF
from deployment.transaction_scoped_research_reader import TransactionScopedResearchReader

class Flow:
    def begin(self):
        return "https://issuer.example/authorize?state=" + "a"*43 + "&code_challenge=synthetic"
class Controller:
    def complete(self, state, code):
        if code != "valid": raise PermissionError()
        return "__Host-alpha_session=" + "s"*48 + "; Path=/; Secure; HttpOnly; SameSite=Lax"
class Sessions:
    revoked = False
    def resolve_owner(self, sid):
        if self.revoked: raise PermissionError()
        return "oidc_" + "a"*64
    def revoke(self, sid): self.revoked = True
class Reader:
    def list_runs(self, owner):
        if owner != "oidc_" + "a"*64: raise PermissionError()
        return [{"run_id":"synthetic"}]
    def summary(self, owner): return {"performance":{"status":"unavailable"}}

class BFFTests(unittest.TestCase):
    def setUp(self):
        self.sessions = Sessions()
        self.limiter = Mock(spec=PostgresIdentityLimiter)
        self.limiter.allow_owner.return_value = True
        reader = Mock(spec=AccountRoleResearchReader, wraps=Reader())
        self.app = StagingResearchBFF(Flow(), Controller(), self.sessions, reader,
                                      origin="https://staging.example", rate_limiter=self.limiter,
                                      authorize_owner=lambda owner: True)
    def call(self, path, method="GET", **env):
        result = {}
        def start(status, headers): result.update(status=status, headers=headers)
        result["body"] = b"".join(self.app({"PATH_INFO":path,"REQUEST_METHOD":method,**env},start))
        return result
    def test_callback_requires_browser_bound_state(self):
        state = "a"*43
        self.assertEqual(self.call("/auth/callback",QUERY_STRING="state="+state+"&code=valid")["status"],"401 Unauthorized")
        result = self.call("/auth/callback",QUERY_STRING="state="+state+"&code=valid",
                           HTTP_COOKIE="__Host-alpha_oauth_state="+state)
        self.assertEqual(result["status"],"303 See Other")
        self.assertEqual(len([h for h in result["headers"] if h[0]=="Set-Cookie"]),2)
    def test_protected_api_and_revocation(self):
        path="/api/v1/research/runs"
        self.assertEqual(self.call(path)["status"],"401 Unauthorized")
        cookie="__Host-alpha_session="+"s"*48
        self.assertEqual(self.call(path,HTTP_COOKIE=cookie)["status"],"200 OK")
        self.assertEqual(self.call("/auth/logout","POST",HTTP_COOKIE=cookie,HTTP_ORIGIN="https://evil.example")["status"],"403 Forbidden")
        self.assertEqual(self.call("/auth/logout","POST",HTTP_COOKIE=cookie,HTTP_ORIGIN="https://staging.example")["status"],"204 No Content")
        self.assertEqual(self.call(path,HTTP_COOKIE=cookie)["status"],"403 Forbidden")
    def test_trading_and_unexpected_routes_denied(self):
        for path in ("/api/trade","/api/v1/orders","/auth/callback"):
            self.assertNotEqual(self.call(path,method="POST")["status"],"200 OK")
    def test_duplicate_cookie_rejected(self):
        cookie="__Host-alpha_session="+"s"*48
        self.assertEqual(self.call("/api/v1/research/runs",HTTP_COOKIE=cookie+"; "+cookie)["status"],"401 Unauthorized")
    def test_legacy_shared_reader_rejected(self):
        legacy = TransactionScopedResearchReader(lambda: self.fail("legacy database connection opened"))
        with self.assertRaisesRegex(ValueError, "tenant-role research reader required"):
            StagingResearchBFF(Flow(), Controller(), self.sessions, legacy,
                               origin="https://staging.example", rate_limiter=self.limiter,
                               authorize_owner=lambda owner: True)

if __name__=="__main__": unittest.main()
