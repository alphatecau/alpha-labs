import unittest
from unittest.mock import patch
from deployment.authenticated_staging_entry import create_application


class EntryTests(unittest.TestCase):
    def setUp(self):
        self.env = {"ALPHA_BFF_ORIGIN": "https://staging.example.test"}
        self.args = dict(environ=self.env, ownership=object(),
                         principal_factory=lambda **k: k,
                         state_connect=lambda: None, session_connect=lambda: None,
                         tenant_connect=lambda: None,
                         trusted_peer_cidrs=["10.1.2.0/24"],
                         readiness_check=lambda: True,
                         verifier_factory=lambda *a: lambda t: None)

    def build(self):
        with patch("deployment.authenticated_staging_entry.build_authenticated_application",
                   return_value=lambda e, s: [b"app"]) as factory:
            app = create_application(**self.args)
            factory.assert_called_once()
            return app

    def call(self, app, path, **overrides):
        env = dict(REMOTE_ADDR="10.1.2.3", HTTP_HOST="staging.example.test",
                   HTTP_X_FORWARDED_PROTO="https", PATH_INFO=path,
                   REQUEST_METHOD="GET")
        env.update(overrides)
        out = []
        body = b"".join(app(env, lambda status, headers: out.append((status, headers))))
        return out[0][0], body

    def test_liveness_never_claims_auth_readiness(self):
        status, body = self.call(self.build(), "/livez")
        self.assertEqual(status, "200 OK")
        self.assertIn(b'"authenticated_ready":false', body)

    def test_readiness_requires_explicit_true(self):
        app = self.build()
        self.assertEqual(self.call(app, "/readyz")[0], "200 OK")
        self.args["readiness_check"] = lambda: False
        self.assertEqual(self.call(self.build(), "/readyz")[0], "503 Service Unavailable")

    def test_readiness_exception_fails_closed(self):
        def failed():
            raise ConnectionError("database unavailable")
        self.args["readiness_check"] = failed
        self.assertEqual(self.call(self.build(), "/readyz")[0], "503 Service Unavailable")

    def test_untrusted_peer_and_spoofed_headers_denied(self):
        app = self.build()
        self.assertEqual(self.call(app, "/readyz", REMOTE_ADDR="198.51.100.2")[0], "403 Forbidden")
        self.assertEqual(self.call(app, "/readyz", HTTP_X_FORWARDED_FOR="10.1.2.3")[0], "403 Forbidden")
        self.assertEqual(self.call(app, "/readyz", HTTP_X_FORWARDED_PROTO="http")[0], "403 Forbidden")

    def test_missing_bindings_and_unrestricted_proxy_fail_startup(self):
        for field, bad in (("readiness_check", None), ("trusted_peer_cidrs", []),
                           ("trusted_peer_cidrs", ["0.0.0.0/0"])):
            with self.subTest(field=field, bad=bad):
                args = dict(self.args, **{field: bad})
                with patch("deployment.authenticated_staging_entry.build_authenticated_application",
                           return_value=lambda e, s: [b"app"]):
                    with self.assertRaises(ValueError):
                        create_application(**args)

    def test_bootstrap_failure_fails_startup(self):
        with patch("deployment.authenticated_staging_entry.build_authenticated_application",
                   side_effect=ValueError("missing secret")):
            with self.assertRaises(ValueError):
                create_application(**self.args)


if __name__ == "__main__":
    unittest.main()
