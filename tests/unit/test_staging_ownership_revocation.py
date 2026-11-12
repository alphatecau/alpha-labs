"""Actual ownership registry with synthetic sessions; no identity-provider access."""
import hashlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from alpha_lab.research.paper_account_service import VerifiedPrincipal
from alpha_lab.research.paper_ownership_registry import PaperOwnershipRegistry
from alpha_lab.research.postgres_paper_security import PostgresIdentityLimiter
from deployment.account_role_research_reader import AccountRoleResearchReader
from deployment.postgres_opaque_sessions import PostgresOpaqueSessions
from deployment.staging_authenticated_bff import StagingResearchBFF


class OwnershipRevocationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.registry = PaperOwnershipRegistry(self.folder.name + "/owners.db")
        self.principal = VerifiedPrincipal(subject="alice", issuer="https://issuer.example/")
        self.owner = "oidc_" + hashlib.sha256(
            (self.principal.issuer + "\0" + self.principal.subject).encode()).hexdigest()
        self.registry.provision(self.principal, "primary")
        self.sessions = SimpleNamespace(resolve_owner=Mock(return_value=self.owner))
        self.reader = Mock(spec=AccountRoleResearchReader)
        self.reader.list_runs.return_value = []
        self.reader.summary.return_value = {}
        self.authorize = Mock(side_effect=lambda owner: self.registry.require_owner_id(owner, "primary"))
        self.app = self.build(self.authorize)

    def tearDown(self):
        self.registry.close()
        self.folder.cleanup()

    def build(self, authorize):
        limiter = Mock(spec=PostgresIdentityLimiter)
        limiter.allow_owner.return_value = True
        return StagingResearchBFF(object(), object(), self.sessions, self.reader,
                                 origin="https://staging.example", rate_limiter=limiter, authorize_owner=authorize)

    def request(self, path="/api/v1/research/runs", **extra):
        response = {}
        body = b"".join(self.app({"PATH_INFO": path, "REQUEST_METHOD": "GET",
                                 "HTTP_COOKIE": "__Host-alpha_session=" + "s" * 48, **extra},
                                lambda code, headers: response.update(status=code, headers=dict(headers))))
        return response["status"], body

    def test_existing_session_loses_both_read_routes_after_ownership_revocation(self):
        for path in ("/api/v1/research/runs", "/api/v1/research/summary"):
            self.assertEqual(self.request(path)[0], "200 OK")
        self.registry.revoke(self.principal, "primary")
        self.reader.list_runs.reset_mock()
        self.reader.summary.reset_mock()
        for path in ("/api/v1/research/runs", "/api/v1/research/summary"):
            self.assertEqual(self.request(path)[0], "403 Forbidden")
        self.reader.list_runs.assert_not_called()
        self.reader.summary.assert_not_called()

    def test_missing_authorizer_rejected_at_construction(self):
        with self.assertRaises(ValueError):
            self.build(None)

    def test_false_or_ambiguous_authorization_does_not_call_reader(self):
        for decision in (False, None, 1, "true"):
            with self.subTest(decision=decision):
                self.app = self.build(lambda owner: decision)
                self.assertEqual(self.request()[0], "403 Forbidden")
        self.reader.list_runs.assert_not_called()

    def test_ownership_outage_is_unavailable_without_data_access(self):
        self.authorize.side_effect = OSError("synthetic registry outage")
        status, body = self.request()
        self.assertEqual(status, "503 Service Unavailable")
        self.assertNotIn(b"outage", body)
        self.reader.list_runs.assert_not_called()

    def test_other_subject_and_same_subject_different_issuer_are_denied(self):
        for subject, issuer in (("bob", self.principal.issuer),
                                (self.principal.subject, "https://other.example/")):
            self.sessions.resolve_owner.return_value = PostgresOpaqueSessions._owner(subject, issuer)
            self.assertEqual(self.request(HTTP_X_OWNER_ID=self.owner,
                                          QUERY_STRING="owner=" + self.owner)[0], "403 Forbidden")
        self.reader.list_runs.assert_not_called()

    def test_malformed_session_owner_never_reaches_ownership_or_reader(self):
        for owner in (None, "oidc_bad", "oidc_" + "A" * 64, {"verified": True}):
            self.sessions.resolve_owner.return_value = owner
            self.assertEqual(self.request()[0], "403 Forbidden")
        self.authorize.assert_not_called()
        self.reader.list_runs.assert_not_called()

    def test_revoked_or_expired_session_never_reaches_ownership(self):
        self.sessions.resolve_owner.side_effect = PermissionError("invalid session")
        self.assertEqual(self.request()[0], "403 Forbidden")
        self.authorize.assert_not_called()
        self.reader.list_runs.assert_not_called()

    def test_session_hash_matches_canonical_verifier_and_ownership_digest(self):
        self.assertEqual(PostgresOpaqueSessions._owner(self.principal.subject, self.principal.issuer), self.owner)
        self.assertTrue(self.registry.require_owner_id(self.owner, "primary"))
        for owner, account in (("oidc_bad", "primary"), (self.owner, "../escape")):
            with self.assertRaises(PermissionError):
                self.registry.require_owner_id(owner, account)


if __name__ == "__main__":
    unittest.main()
