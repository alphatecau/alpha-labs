"""End-to-end offline Auth0 BFF acceptance with disposable PostgreSQL state/sessions.

Auth0 code exchange and signed identity verification are deterministic injected
test doubles. Real durable state, sessions, WSGI routing, ownership gating and
the AccountRoleResearchReader/TenantCredentialBroker path are exercised.
"""
import json
import os
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlsplit

from deployment.account_role_research_reader import AccountRoleResearchReader
from deployment.auth0_pkce_callback import Auth0PKCEFlow, Auth0CallbackController
from deployment.postgres_oauth_state import PostgresOAuthStateStore, SCHEMA as STATE_SCHEMA
from deployment.postgres_opaque_sessions import PostgresOpaqueSessions, SCHEMA as SESSION_SCHEMA
from deployment.staging_authenticated_bff import StagingResearchBFF
from deployment.tenant_credential_broker import TenantCredentialBroker, tenant_login_role


class FakeCursor:
    def __init__(self, owner):
        self.owner = owner
        self.query = ""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        self.query = query
        if "FROM ONLY public.alpha_role_research" in query:
            assert params == (50,)
        elif "session_user = %s" in query:
            assert params == (tenant_login_role(self.owner),)

    def fetchone(self):
        if "SHOW transaction_read_only" in self.query:
            return ("on",)
        return (True,)

    def fetchall(self):
        if "FROM ONLY public.alpha_role_research" in self.query:
            return [("run-a", "hash-a", datetime(2030, 1, 1, tzinfo=timezone.utc))]
        return []


class FakeTenantConnection:
    def __init__(self, owner):
        self.owner = owner

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    @contextmanager
    def transaction(self):
        yield self

    def cursor(self):
        return FakeCursor(self.owner)


@unittest.skipUnless(os.getenv("ALPHA_DISPOSABLE_PG_DSN"), "disposable CI PostgreSQL required")
class IntegratedAuth0BFFTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        cls.dsn = os.environ["ALPHA_DISPOSABLE_PG_DSN"]
        with psycopg.connect(cls.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(STATE_SCHEMA)
                cur.execute(SESSION_SCHEMA)

    def setUp(self):
        import psycopg
        self.connect = lambda: psycopg.connect(self.dsn)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE public.alpha_oauth_transactions, public.alpha_oidc_sessions")
        self.origin = "https://isolated.example"
        self.active = set()
        self.exchange_calls = []
        state = PostgresOAuthStateStore(self.connect)
        self.sessions = PostgresOpaqueSessions(self.connect)
        self.flow = Auth0PKCEFlow(
            issuer="https://auth.example/", client_id="test-client",
            redirect_uri=self.origin + "/auth/callback", state_store=state)
        class Principal:
            subject = "auth0|alice"
            issuer = "https://auth.example/"
        class Verifier:
            def verify(self, token, *, expected_nonce):
                if token != "signed-token" or not expected_nonce:
                    raise PermissionError("invalid signed identity")
                return Principal()
        def exchange(**kwargs):
            self.exchange_calls.append(kwargs)
            return {"id_token": "signed-token"}
        self.owner = self.sessions._owner("auth0|alice", "https://auth.example/")
        self.active.add(self.owner)
        self.controller = Auth0CallbackController(
            flow=self.flow, exchange_code=exchange,
            token_verifier=Verifier(), sessions=self.sessions,
            authorise_principal=lambda p: self.sessions._owner(p.subject, p.issuer) in self.active)
        def secret_for(owner):
            return {"host": "isolated.example", "port": 5432, "dbname": "disposable",
                    "user": tenant_login_role(owner), "password": "test-only"}
        def tenant_connect(**kwargs):
            owner = next((o for o in self.active if tenant_login_role(o) == kwargs["user"]), None)
            if owner is None:
                raise PermissionError("unprovisioned account")
            return FakeTenantConnection(owner)
        reader = AccountRoleResearchReader(TenantCredentialBroker(secret_for, tenant_connect))
        self.app = StagingResearchBFF(
            self.flow, self.controller, self.sessions, reader, origin=self.origin,
            authorize_owner=lambda owner: owner in self.active)

    def request(self, path, *, method="GET", cookie="", query="", origin=None, accept=""):
        response = {}
        def start(status, headers):
            response["status"] = int(status.split()[0])
            response["headers"] = headers
        env = {"PATH_INFO": path, "REQUEST_METHOD": method, "HTTP_COOKIE": cookie,
               "QUERY_STRING": query, "HTTP_ACCEPT": accept}
        if origin is not None:
            env["HTTP_ORIGIN"] = origin
        response["body"] = b"".join(self.app(env, start))
        return response

    @staticmethod
    def cookie(response, name):
        for key, value in response["headers"]:
            if key == "Set-Cookie" and value.startswith(name + "="):
                return value.split(";", 1)[0]
        raise AssertionError("missing cookie " + name)

    def login(self):
        first = self.request("/auth/login")
        self.assertEqual(first["status"], 302)
        url = next(v for k, v in first["headers"] if k == "Location")
        state = parse_qs(urlsplit(url).query)["state"][0]
        state_cookie = self.cookie(first, "__Host-alpha_oauth_state")
        callback = self.request("/auth/callback", query="code=code&state=" + state, cookie=state_cookie)
        self.assertEqual(callback["status"], 303)
        return state, state_cookie, self.cookie(callback, "__Host-alpha_session")

    def test_full_login_research_logout_and_revocation(self):
        state, state_cookie, sid = self.login()
        runs = self.request("/api/v1/research/runs", cookie=sid)
        self.assertEqual(runs["status"], 200)
        self.assertEqual(json.loads(runs["body"])["data"][0]["run_id"], "run-a")
        summary = self.request("/api/v1/research/summary", cookie=sid)
        self.assertEqual(summary["status"], 200)
        self.assertEqual(json.loads(summary["body"])["data"]["recent_run_count"], 1)
        self.assertEqual(self.request("/auth/callback", query="code=code&state=" + state,
                                      cookie=state_cookie)["status"], 401)
        self.assertEqual(len(self.exchange_calls), 1)
        self.assertEqual(self.request("/auth/logout", method="POST", cookie=sid,
                                      origin="https://attacker.example")["status"], 403)
        self.assertEqual(self.request("/auth/logout", method="POST", cookie=sid,
                                      origin=self.origin)["status"], 204)
        self.assertNotEqual(self.request("/api/v1/research/runs", cookie=sid)["status"], 200)

    def test_browser_landing_dashboard_and_logout(self):
        entry = self.request("/dashboard")
        self.assertEqual((entry["status"], dict(entry["headers"])["Location"]), (303, "/auth/login"))
        _, _, sid = self.login()
        for path in ("/", "/dashboard"):
            page = self.request(path, cookie=sid)
            self.assertEqual(page["status"], 200)
            self.assertIn(b"run-a", page["body"])
            self.assertIn(b'action="/auth/logout"', page["body"])
            self.assertEqual(dict(page["headers"])["Cache-Control"], "no-store")
            self.assertNotIn(sid.encode(), page["body"])
        logout = self.request("/auth/logout", method="POST", cookie=sid, origin=self.origin, accept="text/html")
        dest = urlsplit(dict(logout["headers"])["Location"])
        self.assertEqual((logout["status"], dest.netloc, dest.path), (303, "auth.example", "/v2/logout"))
        self.assertEqual(parse_qs(dest.query)["returnTo"], [self.origin + "/signed-out"])
        self.assertIn("Max-Age=0", dict(logout["headers"])["Set-Cookie"])
        self.assertEqual(self.request("/dashboard", cookie=sid)["status"], 403)
        self.assertIn(b"Your Alpha Labs session has ended", self.request("/signed-out")["body"])

    def test_missing_cookie_and_deprovisioned_owner_denied(self):
        self.assertEqual(self.request("/api/v1/research/runs")["status"], 401)
        _, _, sid = self.login()
        self.active.clear()
        self.assertEqual(self.request("/api/v1/research/runs", cookie=sid)["status"], 403)
        self.assertEqual(self.request("/api/v1/research/summary", cookie=sid)["status"], 403)

    def test_browser_state_binding_and_read_only_surface(self):
        first = self.request("/auth/login")
        url = next(v for k, v in first["headers"] if k == "Location")
        state = parse_qs(urlsplit(url).query)["state"][0]
        self.assertEqual(self.request("/auth/callback", query="code=code&state=" + state)["status"], 401)
        self.assertEqual(self.request("/auth/callback", query="code=code&state=" + state,
                                      cookie="__Host-alpha_oauth_state=wrong")["status"], 401)
        self.assertEqual(self.exchange_calls, [])
        self.assertEqual(self.request("/api/v1/research/runs", method="POST")["status"], 404)
        self.assertEqual(self.request("/api/v1/orders", method="POST")["status"], 404)
        self.assertIn(b'"trading":"disabled"', self.request("/healthz")["body"])


    def test_login_state_database_outage_fails_closed(self):
        original = self.flow.begin
        self.flow.begin = lambda: (_ for _ in ()).throw(
            ConnectionError("simulated OAuth state-store outage"))
        try:
            response = self.request("/auth/login")
            self.assertEqual(response["status"], 503)
            self.assertEqual(response["body"], b"")
            self.assertFalse(any(k in ("Location", "Set-Cookie") for k, _ in response["headers"]))
        finally:
            self.flow.begin = original
        self.assertEqual(self.request("/auth/login")["status"], 302)

    def test_session_database_outage_fails_closed(self):
        _, _, sid = self.login()
        original = self.sessions.resolve_owner
        self.sessions.resolve_owner = lambda token: (_ for _ in ()).throw(
            ConnectionError("simulated session database outage"))
        try:
            response = self.request("/api/v1/research/runs", cookie=sid)
            self.assertEqual(response["status"], 503)
            self.assertNotIn(b"run-a", response["body"])
        finally:
            self.sessions.resolve_owner = original
        self.assertEqual(self.request("/api/v1/research/runs", cookie=sid)["status"], 200)

    def test_ownership_database_outage_fails_closed(self):
        _, _, sid = self.login()
        original = self.app.authorize_owner
        self.app.authorize_owner = lambda owner: (_ for _ in ()).throw(
            ConnectionError("simulated ownership database outage"))
        try:
            self.assertEqual(self.request("/api/v1/research/runs", cookie=sid)["status"], 503)
            self.assertEqual(self.request("/api/v1/research/summary", cookie=sid)["status"], 503)
        finally:
            self.app.authorize_owner = original

    def test_tenant_credential_failure_fails_closed(self):
        _, _, sid = self.login()
        original = self.app.reader.list_runs
        self.app.reader.list_runs = lambda owner: (_ for _ in ()).throw(
            PermissionError("tenant credential revoked"))
        try:
            self.assertEqual(self.request("/api/v1/research/runs", cookie=sid)["status"], 403)
            self.assertNotIn(b"run-a", self.request("/api/v1/research/runs", cookie=sid)["body"])
        finally:
            self.app.reader.list_runs = original

    def test_research_database_outage_fails_closed(self):
        _, _, sid = self.login()
        original = self.app.reader.list_runs
        self.app.reader.list_runs = lambda owner: (_ for _ in ()).throw(
            ConnectionError("tenant database unavailable"))
        try:
            self.assertEqual(self.request("/api/v1/research/runs", cookie=sid)["status"], 503)
            self.assertEqual(self.request("/api/v1/research/summary", cookie=sid)["status"], 503)
        finally:
            self.app.reader.list_runs = original

    def test_verified_unprovisioned_user_gets_no_session(self):
        self.active.clear()
        first = self.request("/auth/login")
        state = parse_qs(urlsplit(dict(first["headers"])["Location"]).query)["state"][0]
        response = self.request("/auth/callback", query="code=code&state=" + state,
                                cookie=self.cookie(first, "__Host-alpha_oauth_state"), accept="text/html")
        self.assertEqual(response["status"], 403)
        self.assertIn(b"Research access required", response["body"])
        self.assertFalse(any(k == "Set-Cookie" and v.startswith("__Host-alpha_session=")
                             for k, v in response["headers"]))

    def test_callback_token_exchange_failure_no_session(self):
        first = self.request("/auth/login")
        url = next(v for k, v in first["headers"] if k == "Location")
        state = parse_qs(urlsplit(url).query)["state"][0]
        cookie = self.cookie(first, "__Host-alpha_oauth_state")
        self.controller.exchange_code = lambda **kwargs: (_ for _ in ()).throw(
            ConnectionError("Auth0 token endpoint unavailable"))
        failed = self.request("/auth/callback", query="code=code&state=" + state, cookie=cookie)
        self.assertEqual(failed["status"], 401)
        self.assertFalse(any(k == "Set-Cookie" and v.startswith("__Host-alpha_session=")
                             for k, v in failed["headers"]))
        self.assertEqual(self.request("/api/v1/research/runs")["status"], 401)

    def test_malformed_callback_never_exchanges_code(self):
        first = self.request("/auth/login")
        url = next(v for k, v in first["headers"] if k == "Location")
        state = parse_qs(urlsplit(url).query)["state"][0]
        cookie = self.cookie(first, "__Host-alpha_oauth_state")
        for query in ("code=x&code=y&state=" + state,
                      "code=&state=" + state,
                      "code=x&state=" + state + "&unexpected=1",
                      "state=" + state,
                      "code=x&state="):
            with self.subTest(query=query):
                self.assertEqual(self.request("/auth/callback", query=query, cookie=cookie)["status"], 401)
        self.assertEqual(self.exchange_calls, [])

    def test_revocation_blocks_research_immediately(self):
        _, _, sid = self.login()
        self.assertEqual(self.request("/api/v1/research/runs", cookie=sid)["status"], 200)
        self.active.remove(self.owner)
        self.assertEqual(self.request("/api/v1/research/runs", cookie=sid)["status"], 403)
        self.assertEqual(self.request("/api/v1/research/summary", cookie=sid)["status"], 403)
        self.active.add(self.owner)
        self.assertEqual(self.request("/api/v1/research/runs", cookie=sid)["status"], 200)


if __name__ == "__main__":
    unittest.main()
