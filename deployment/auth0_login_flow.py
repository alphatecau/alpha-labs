"""Server-side Auth0 OIDC authorization request preparation and callback checks.

No network or session persistence: caller must use trusted HTTPS token exchange,
pinned JWKS validation, atomic one-use state storage and secure cookie issuance.
"""
import base64
import hashlib
import hmac
import secrets
import time
import urllib.parse


def _url64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


class Auth0LoginFlow:
    def __init__(self, *, issuer, client_id, redirect_uri, state_store, clock=None):
        p = urllib.parse.urlsplit(issuer)
        r = urllib.parse.urlsplit(redirect_uri)
        if (p.scheme != "https" or not p.hostname or p.query or p.fragment or p.path not in ("", "/")
                or r.scheme != "https" or not r.hostname or r.fragment or
                not isinstance(client_id, str) or not client_id or
                not callable(getattr(state_store, "put", None)) or
                not callable(getattr(state_store, "consume", None))):
            raise ValueError("trusted Auth0 HTTPS configuration and state store required")
        self.issuer = issuer.rstrip("/")
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.store = state_store
        self.clock = clock or time.time

    def begin(self):
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = _url64(hashlib.sha256(verifier.encode()).digest())
        self.store.put(hashlib.sha256(state.encode()).hexdigest(),
                       {"nonce": nonce, "verifier": verifier, "created_at": int(self.clock())}, 300)
        params = {"response_type": "code", "client_id": self.client_id,
                  "redirect_uri": self.redirect_uri, "scope": "openid profile",
                  "state": state, "nonce": nonce,
                  "code_challenge": challenge, "code_challenge_method": "S256"}
        return self.issuer + "/authorize?" + urllib.parse.urlencode(params)

    def validate_callback(self, *, state, code, id_token, verifier):
        if not all(isinstance(v, str) and 1 <= len(v) <= 8192 for v in (state, code, id_token)):
            raise PermissionError("invalid callback")
        record = self.store.consume(hashlib.sha256(state.encode()).hexdigest())
        if not isinstance(record, dict) or not 0 <= self.clock() - record.get("created_at", -1) <= 300:
            raise PermissionError("expired or reused login state")
        claims = verifier(id_token)
        if (not isinstance(claims, dict) or claims.get("verified") is not True or
                not isinstance(claims.get("nonce"), str) or
                not hmac.compare_digest(claims["nonce"], record["nonce"])):
            raise PermissionError("invalid OIDC nonce")
        return {"code": code, "pkce_verifier": record["verifier"], "identity": claims}
