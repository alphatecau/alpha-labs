import unittest
from contextlib import nullcontext
from unittest.mock import MagicMock
from deployment.auth0_login_flow import Auth0LoginFlow
from deployment.tenant_credential_broker import (
    TenantCredentialBroker,
    tenant_login_role,
)


class Store:
    def __init__(self):
        self.data = {}

    def put(self, key, value, ttl):
        self.data[key] = value

    def consume(self, key):
        return self.data.pop(key, None)


class SecurityPreparationTests(unittest.TestCase):
    def test_auth0_pkce_and_one_use_nonce(self):
        store = Store()
        flow = Auth0LoginFlow(
            issuer="https://tenant.auth0.com",
            client_id="client",
            redirect_uri="https://dashboard.example/callback",
            state_store=store,
            clock=lambda: 1000,
        )
        from urllib.parse import urlsplit, parse_qs

        params = parse_qs(urlsplit(flow.begin()).query)
        self.assertEqual(params["code_challenge_method"], ["S256"])
        self.assertNotIn("code_verifier", params)
        state = params["state"][0]
        nonce = params["nonce"][0]
        result = flow.validate_callback(
            state=state,
            code="synthetic-code",
            id_token="synthetic-token",
            verifier=lambda token: {"verified": True, "nonce": nonce},
        )
        self.assertTrue(result["pkce_verifier"])
        with self.assertRaises(PermissionError):
            flow.validate_callback(
                state=state,
                code="synthetic-code",
                id_token="synthetic-token",
                verifier=lambda token: {"verified": True, "nonce": nonce},
            )

    def test_auth0_wrong_nonce_denied(self):
        flow = Auth0LoginFlow(
            issuer="https://tenant.auth0.com",
            client_id="client",
            redirect_uri="https://dashboard.example/callback",
            state_store=Store(),
            clock=lambda: 1000,
        )
        from urllib.parse import urlsplit, parse_qs

        state = parse_qs(urlsplit(flow.begin()).query)["state"][0]
        with self.assertRaises(PermissionError):
            flow.validate_callback(
                state=state,
                code="code",
                id_token="token",
                verifier=lambda token: {"verified": True, "nonce": "forged"},
            )

    def test_broker_fails_closed_without_credentials(self):
        broker = TenantCredentialBroker(
            lambda owner: None, lambda **kwargs: self.fail("must not connect")
        )
        with self.assertRaises(PermissionError):
            with broker("oidc_" + "a" * 64):
                pass

    def test_broker_rejects_unsafe_login_read_only_setting_and_table(self):
        owner = "oidc_" + "a" * 64
        connection = MagicMock()
        connection.transaction.return_value = nullcontext()
        cursor = connection.cursor.return_value.__enter__.return_value
        broker = TenantCredentialBroker(
            lambda owner: {
                "host": "db.example",
                "port": 5432,
                "dbname": "research",
                "user": tenant_login_role(owner),
                "password": "synthetic",
            },
            lambda **kwargs: nullcontext(connection),
        )
        for rows in ([(False,)], [(True,), ("off",)], [(True,), ("on",), (False,)]):
            with self.subTest(rows=rows), self.assertRaises(PermissionError):
                cursor.fetchone.side_effect = rows
                with broker(owner):
                    self.fail("unsafe configuration yielded a connection")


if __name__ == "__main__":
    unittest.main()
