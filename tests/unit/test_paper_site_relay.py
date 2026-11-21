"""Offline tests for fail-closed paper-only authenticated BFF route."""
import json
import unittest
from unittest.mock import Mock

from deployment.paper_site import RelayBudget
from deployment.staging_authenticated_bff import StagingResearchBFF

OWNER = "oidc_" + "a" * 64


def request(app, *, cookie="__Host-alpha_session=valid"):
    response = []
    body = b"".join(app({"PATH_INFO": "/api/v1/paper/snapshot",
                         "REQUEST_METHOD": "GET", "HTTP_COOKIE": cookie},
                        lambda status, headers: response.append((status, headers))))
    return response[0][0], body


def make_app(*, reader=None, owner=OWNER, authorised=True):
    app = object.__new__(StagingResearchBFF)
    app.sessions = Mock()
    app.sessions.resolve_owner.return_value = owner
    app.authorize_owner = lambda value: authorised
    app.paper_reader = reader
    app.paper_budget = RelayBudget()
    app.revision = "a" * 40
    return app


class PaperRelayTests(unittest.TestCase):
    def test_missing_session_refused(self):
        status, _ = request(make_app(reader=Mock()), cookie="")
        self.assertEqual(status, "401 Unauthorized")

    def test_unverified_identity_refused(self):
        status, _ = request(make_app(reader=Mock(), owner="unknown"))
        self.assertEqual(status, "401 Unauthorized")

    def test_revoked_ownership_refused(self):
        reader = Mock()
        status, _ = request(make_app(reader=reader, authorised=False))
        self.assertEqual(status, "403 Forbidden")
        reader.snapshot.assert_not_called()

    def test_unconfigured_paper_reader_fails_closed(self):
        status, _ = request(make_app())
        self.assertEqual(status, "503 Service Unavailable")

    def test_tenant_bound_snapshot_and_simulation_only(self):
        reader = Mock()
        reader.snapshot.return_value = {"events": 3, "account": OWNER}
        status, body = request(make_app(reader=reader))
        self.assertEqual(status, "200 OK")
        self.assertEqual(json.loads(body)["trading"], "disabled")
        self.assertEqual(json.loads(body)["mode"], "paper_only")
        reader.snapshot.assert_called_once_with(OWNER)

    def test_reader_failure_fails_closed(self):
        reader = Mock()
        reader.snapshot.side_effect = RuntimeError("journal unavailable")
        status, _ = request(make_app(reader=reader))
        self.assertEqual(status, "503 Service Unavailable")

    def test_post_cannot_execute_orders(self):
        app = make_app(reader=Mock())
        result = []
        app({"PATH_INFO": "/api/v1/paper/snapshot", "REQUEST_METHOD": "POST",
             "HTTP_COOKIE": "__Host-alpha_session=valid"},
            lambda status, headers: result.append(status))
        self.assertEqual(result, ["404 Not Found"])


if __name__ == "__main__":
    unittest.main()
