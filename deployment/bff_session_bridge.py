"""Research-only session/ownership bridge for an external BFF.

The authenticated principal comes from the durable OIDC session store.
The registry must explicitly authorise that principal for the primary account.
No browser-supplied account identifier is consulted.
This is a library adapter, not a deployed HTTP service.
"""
import hashlib
from http.cookies import SimpleCookie

from alpha_lab.research.paper_account_service import VerifiedPrincipal


class SessionOwnershipVerifier:
    def __init__(self, *, sessions, ownership, limiter):
        if not all((hasattr(sessions, "authenticate"), hasattr(ownership, "require"),
                    hasattr(limiter, "allow"))):
            raise ValueError("session, ownership and limiter required")
        self.sessions = sessions
        self.ownership = ownership
        self.limiter = limiter

    def __call__(self, session_cookie):
        try:
            if not isinstance(session_cookie, str) or len(session_cookie) > 4096:
                raise PermissionError("invalid cookie")
            jar = SimpleCookie()
            jar.load(session_cookie)
            if set(jar.keys()) != {"__Host-alpha_session"}:
                raise PermissionError("invalid cookie set")
            sid = jar["__Host-alpha_session"].value
            subject, issuer = self.sessions.authenticate(sid)
            principal = VerifiedPrincipal(subject=subject, issuer=issuer)
            self.limiter.allow(issuer, subject)
            self.ownership.require(principal, "primary")
            # Same canonical identity derivation as the pinned OIDC verifier.
            owner = "oidc_" + hashlib.sha256((issuer + "\x00" + subject).encode()).hexdigest()
            return {"verified": True, "owner_id": owner}
        except Exception as exc:
            raise PermissionError("session or account not authorised") from exc
