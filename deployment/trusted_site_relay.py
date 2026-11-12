"""Trusted server-side relay. Identity verification and HTTPS transport are injected.

Not a browser bundle. Refuses operation without an independently verified session.
"""
import json
import re
from deployment.research_readonly_api import sign_assertion

class TrustedSiteRelay:
    def __init__(self, verify_session, backend_get, signing_secret):
        if not callable(verify_session) or not callable(backend_get):
            raise ValueError("trusted session verifier and backend transport required")
        self.verify_session = verify_session
        self.backend_get = backend_get
        self.signing_secret = signing_secret

    def fetch(self, session_credential, resource):
        if resource not in ("runs", "summary"):
            raise ValueError("unsupported read-only resource")
        identity = self.verify_session(session_credential)
        if not isinstance(identity, dict) or identity.get("verified") is not True:
            raise PermissionError("unverified identity")
        owner = identity.get("owner_id")
        if not isinstance(owner, str) or not re.fullmatch("[A-Za-z0-9_-]{1,128}", owner):
            raise PermissionError("invalid owner identity")
        token = sign_assertion(owner, self.signing_secret)
        # Transport must use TLS, fixed backend origin, strict timeout, no redirects,
        # and must not forward browser-supplied Authorization or owner identifiers.
        result = self.backend_get("/api/v1/research/" + resource,
                                  {"Authorization": "Bearer " + token,
                                   "Accept": "application/json"})
        if not isinstance(result, dict) or result.get("status") != "verified_source":
            raise RuntimeError("research data unavailable")
        return result
