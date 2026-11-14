"""Offline confidential-client token exchange checks; no Auth0 credentials used."""
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs
from deployment.auth0_session_controller import Auth0SessionController

class Flow:
    issuer = "https://tenant.example.auth0.com"
    client_id = "synthetic-client"
    redirect_uri = "https://staging.example/auth/callback"

class Response:
    status = 200
    class Headers:
        def get_content_type(self): return "application/json"
    headers = Headers()
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, count): return b'{"id_token":"synthetic-id-token"}'

class ExchangeTests(unittest.TestCase):
    def test_secret_sent_only_in_server_side_post(self):
        observed = {}
        class Opener:
            def open(self, req, timeout):
                observed["url"] = req.full_url
                observed["method"] = req.get_method()
                observed["body"] = parse_qs(req.data.decode())
                return Response()
        controller = Auth0SessionController(Flow(), None, None, None, None,
                                            client_secret="synthetic-secret-value")
        with patch("deployment.auth0_session_controller.urllib.request.build_opener", return_value=Opener()):
            self.assertEqual(controller._exchange("code", "pkce"), "synthetic-id-token")
        self.assertEqual(observed["method"], "POST")
        self.assertEqual(observed["url"], Flow.issuer + "/oauth/token")
        self.assertEqual(observed["body"]["client_secret"], ["synthetic-secret-value"])
        self.assertNotIn("synthetic-secret-value", observed["url"])
        self.assertEqual(observed["body"]["code_verifier"], ["pkce"])

    def test_invalid_secret_fails_closed(self):
        for secret in ("", "short", 123):
            with self.subTest(secret=secret), self.assertRaises(ValueError):
                Auth0SessionController(Flow(), None, None, None, None, client_secret=secret)

if __name__ == "__main__":
    unittest.main()
