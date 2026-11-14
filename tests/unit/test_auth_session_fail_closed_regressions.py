"""Synthetic fail-closed regression tests for Auth0 callback and opaque sessions.

These tests do not substitute for real Auth0, PostgreSQL RLS or staging.
"""
import hashlib
import unittest
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

from deployment.auth0_login_flow import Auth0LoginFlow
from deployment.postgres_opaque_sessions import PostgresOpaqueSessions


class OneUseState:
    def __init__(self):
        self.records = {}

    def put(self, digest, record, ttl):
        self.records[digest] = dict(record)

    def consume(self, digest):
        return self.records.pop(digest, None)


class CallbackNegativeTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.state_store = OneUseState()
        self.flow = Auth0LoginFlow(
            issuer="https://tenant.example.auth0.com",
            client_id="synthetic-client",
            redirect_uri="https://bff.example/auth/callback",
            state_store=self.state_store,
            clock=lambda: self.now,
        )

    def begin(self):
        state = parse_qs(urlsplit(self.flow.begin()).query)["state"][0]
        record = self.state_store.records[hashlib.sha256(state.encode()).hexdigest()]
        return state, record

    def callback(self, state, claims, code="synthetic-code"):
        return self.flow.validate_callback(
            state=state,
            code=code,
            id_token="synthetic-id-token",
            verifier=lambda _: claims,
        )

    def test_unknown_state_rejected(self):
        with self.assertRaises(PermissionError):
            self.callback("unknown-state", {"verified": True, "nonce": "fake"})

    def test_expired_state_rejected_and_consumed(self):
        state, record = self.begin()
        self.now += 301
        with self.assertRaises(PermissionError):
            self.callback(state, {"verified": True, "nonce": record["nonce"]})
        self.assertFalse(self.state_store.records)

    def test_future_dated_state_rejected(self):
        state, record = self.begin()
        self.now -= 1
        with self.assertRaises(PermissionError):
            self.callback(state, {"verified": True, "nonce": record["nonce"]})

    def test_unverified_identity_rejected_and_consumed(self):
        state, record = self.begin()
        with self.assertRaises(PermissionError):
            self.callback(state, {"verified": False, "nonce": record["nonce"]})
        with self.assertRaises(PermissionError):
            self.callback(state, {"verified": True, "nonce": record["nonce"]})

    def test_missing_or_malformed_nonce_rejected(self):
        for nonce in (None, 123, "incorrect"):
            with self.subTest(nonce=nonce):
                state, _ = self.begin()
                with self.assertRaises(PermissionError):
                    self.callback(state, {"verified": True, "nonce": nonce})

    def test_empty_authorisation_code_rejected(self):
        state, record = self.begin()
        with self.assertRaises(PermissionError):
            self.callback(state, {"verified": True, "nonce": record["nonce"]}, code="")


class OpaqueSessionNegativeTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def test_token_validation_rejects_malformed_values(self):
        for token in (None, "", "short", "a" * 257, "a" * 31, "a" * 32 + "!", "a b" * 12):
            with self.subTest(token=token):
                with self.assertRaises(PermissionError):
                    PostgresOpaqueSessions._hash(token)

    def test_owner_mapping_is_stable_and_tenant_distinct(self):
        owner = PostgresOpaqueSessions._owner
        first = owner("alice", "https://issuer-a.example/")
        self.assertEqual(first, owner("alice", "https://issuer-a.example/"))
        self.assertNotEqual(first, owner("bob", "https://issuer-a.example/"))
        self.assertNotEqual(first, owner("alice", "https://issuer-b.example/"))

    def test_unverified_identity_values_rejected(self):
        owner = PostgresOpaqueSessions._owner
        for subject, issuer in (("", "https://issuer.example/"), (None, "https://issuer.example/"),
                                ("alice", "http://issuer.example/"), ("alice", None)):
            with self.subTest(subject=subject, issuer=issuer):
                with self.assertRaises(PermissionError):
                    owner(subject, issuer)


if __name__ == "__main__":
    unittest.main()
