"""Auth0 authorisation-code + PKCE callback controller for isolated staging.

Requires an injected durable atomic state store, HTTPS token exchanger,
Auth0IDTokenVerifier and opaque session repository. No network or secrets are
read implicitly. The callback consumes state BEFORE exchanging the code.
"""
import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode, urlsplit


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


class Auth0PKCEFlow:
    def __init__(self, *, issuer, client_id, redirect_uri, state_store, clock=time.time):
        issuer_parts = urlsplit(issuer)
        redirect = urlsplit(redirect_uri)
        if (issuer_parts.scheme != "https" or not issuer_parts.hostname or
                issuer_parts.path not in ("", "/") or issuer_parts.query or issuer_parts.fragment or
                issuer_parts.username or issuer_parts.password or issuer_parts.port not in (None, 443) or
                redirect.scheme != "https" or not redirect.hostname or
                redirect.path != "/auth/callback" or redirect.query or redirect.fragment or
                redirect.username or redirect.password or redirect.port not in (None, 443)):
            raise ValueError("exact HTTPS issuer and callback required")
        if not isinstance(client_id, str) or not client_id or state_store is None:
            raise ValueError("client ID and durable state store required")
        self.issuer = issuer.rstrip("/") + "/"
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.state_store = state_store
        self.clock = clock

    def begin(self):
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        nonce = secrets.token_urlsafe(32)
        # The store must implement atomic, expiring, one-time consume.
        self.state_store.put(state, {"verifier": verifier, "nonce": nonce,
                                     "expires": int(self.clock()) + 300})
        params = {
            "response_type": "code", "client_id": self.client_id,
            "redirect_uri": self.redirect_uri, "scope": "openid profile email",
            "state": state, "nonce": nonce, "code_challenge_method": "S256",
            "code_challenge": _b64(hashlib.sha256(verifier.encode()).digest()),
        }
        return self.issuer + "authorize?" + urlencode(params)


class Auth0CallbackController:
    def __init__(self, *, flow, exchange_code, token_verifier, sessions,
                 authorise_principal):
        if not all(callable(x) for x in (exchange_code, authorise_principal)):
            raise ValueError("trusted token exchanger and authoriser required")
        self.flow = flow
        self.exchange_code = exchange_code
        self.token_verifier = token_verifier
        self.sessions = sessions
        self.authorise_principal = authorise_principal

    def complete(self, state, code):
        if not isinstance(state, str) or len(state) < 32 or not isinstance(code, str) or not code:
            raise PermissionError("invalid callback")
        # Atomic consume must delete state even if code exchange or verification fails.
        transaction = self.flow.state_store.consume(state)
        if not isinstance(transaction, dict) or transaction.get("expires", 0) <= self.flow.clock():
            raise PermissionError("expired or replayed callback")
        verifier, nonce = transaction.get("verifier"), transaction.get("nonce")
        if not isinstance(verifier, str) or not isinstance(nonce, str):
            raise PermissionError("invalid OAuth transaction")
        tokens = self.exchange_code(code=code, code_verifier=verifier,
                                    redirect_uri=self.flow.redirect_uri,
                                    client_id=self.flow.client_id)
        if not isinstance(tokens, dict) or not isinstance(tokens.get("id_token"), str):
            raise PermissionError("missing ID token")
        principal = self.token_verifier.verify(tokens["id_token"], expected_nonce=nonce)
        if self.authorise_principal(principal) is not True:
            raise PermissionError("unprovisioned identity")
        sid = self.sessions.create(principal.subject, principal.issuer)
        return "__Host-alpha_session=" + sid + "; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=1800"
