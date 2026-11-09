"""Research-only Auth0 callback: exchange code before accepting ID token."""
import hashlib
import hmac
import json
import ssl
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PermissionError("redirect rejected")


class Auth0SessionController:
    def __init__(self, flow, verify_token, sessions, ownership, principal_factory, exchange=None, client_secret=None):
        self.flow, self.verify_token = flow, verify_token
        self.sessions, self.ownership = sessions, ownership
        self.principal_factory = principal_factory
        self.exchange = exchange or self._exchange
        if client_secret is not None and (not isinstance(client_secret, str) or len(client_secret) < 16):
            raise ValueError("invalid confidential client secret")
        self._client_secret = client_secret

    def _exchange(self, code, verifier):
        params = {"grant_type": "authorization_code", "client_id": self.flow.client_id,
                  "code": code, "code_verifier": verifier,
                  "redirect_uri": self.flow.redirect_uri}
        if self._client_secret is not None:
            params["client_secret"] = self._client_secret
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(
            self.flow.issuer + "/oauth/token", data=data, method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "Accept": "application/json"})
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ssl.create_default_context()), NoRedirect())
        with opener.open(req, timeout=5) as response:
            if response.status != 200 or response.headers.get_content_type() != "application/json":
                raise PermissionError("token exchange failed")
            data = response.read(65537)
            if len(data) > 65536:
                raise PermissionError("token response too large")
            token = json.loads(data).get("id_token")
            if not isinstance(token, str):
                raise PermissionError("missing ID token")
            return token

    def complete(self, state, code):
        if not isinstance(state, str) or not 20 <= len(state) <= 256 or not isinstance(code, str) or not 1 <= len(code) <= 2048:
            raise PermissionError("invalid callback")
        record = self.flow.store.consume(hashlib.sha256(state.encode()).hexdigest())
        if not isinstance(record, dict) or not 0 <= self.flow.clock() - record.get("created_at", -1) <= 300:
            raise PermissionError("expired or replayed state")
        token = self.exchange(code, record["verifier"])
        identity = self.verify_token(token)
        if (identity.get("verified") is not True or
                identity.get("issuer") != self.flow.issuer or
                not isinstance(identity.get("subject"), str) or
                not isinstance(identity.get("nonce"), str) or
                not hmac.compare_digest(identity["nonce"], record["nonce"])):
            raise PermissionError("invalid verified identity")
        principal = self.principal_factory(subject=identity["subject"], issuer=identity["issuer"])
        self.ownership.require(principal, "primary")
        sid = self.sessions.create(identity["subject"], identity["issuer"])
        return "__Host-alpha_session=" + sid + "; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=1800"
