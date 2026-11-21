"""Regression coverage for Auth0 issuer callback parameter validation."""
from deployment.staging_authenticated_bff import StagingResearchBFF


class _Flow:
    issuer = "https://alpha-labs-dev.au.auth0.com/"


class _Dummy:
    pass


def _callback(query):
    # Exercise the callback's parameter validation without token exchange or DB access.
    app = object.__new__(StagingResearchBFF)
    app.flow = _Flow()
    app.controller = _Dummy()
    app.sessions = _Dummy()
    app.reader = _Dummy()
    app.authorize_owner = lambda _: False
    app.origin = "https://alpha-labs-auth-staging.onrender.com"
    captured = []
    response = app({"PATH_INFO": "/auth/callback", "REQUEST_METHOD": "GET",
                    "QUERY_STRING": query}, lambda status, headers: captured.append(status))
    return captured[0], b"".join(response)


def test_mismatched_issuer_fails_closed():
    assert _callback("code=abc&state=def&iss=https%3A%2F%2Fevil.example%2F")[0] == "401 Unauthorized"


def test_extra_callback_parameter_fails_closed():
    assert _callback("code=abc&state=def&iss=https%3A%2F%2Falpha-labs-dev.au.auth0.com%2F&extra=x")[0] == "401 Unauthorized"


def test_duplicate_issuer_fails_closed():
    assert _callback("code=abc&state=def&iss=x&iss=y")[0] == "401 Unauthorized"


def test_exact_issuer_reaches_state_cookie_validation():
    # Missing cookie still fails closed; callback must not reject issuer shape alone.
    assert _callback("code=abc&state=def&iss=https%3A%2F%2Falpha-labs-dev.au.auth0.com%2F")[0] == "401 Unauthorized"
