"""Opt-in Auth0 research staging entry point. No OAuth login or trade routes.

Requires pinned public JWKS supplied via server environment. Fails startup
when keys, audience, issuer, owner subject or persistent storage are absent.
"""
import json
import os
from pathlib import Path
from alpha_lab.research.auth0_jwt import Auth0JWTVerifier
from alpha_lab.research.paper_account_service import PaperAccountService, VerifiedPrincipal
from alpha_lab.research.paper_status_wsgi import PaperStatusWSGI


def build_auth0_app(config):
    required = ("ALPHA_AUTH0_ISSUER", "ALPHA_AUTH0_AUDIENCE", "ALPHA_AUTH0_JWKS_JSON",
                "ALPHA_AUTH0_OWNER_SUBJECT", "ALPHA_PAPER_DATA_DIR")
    if any(not isinstance(config.get(k), str) or not config[k] for k in required):
        raise RuntimeError("Missing Auth0 staging configuration")
    try:
        jwks = json.loads(config["ALPHA_AUTH0_JWKS_JSON"])
        verifier = Auth0JWTVerifier(issuer=config["ALPHA_AUTH0_ISSUER"],
                                   audience=config["ALPHA_AUTH0_AUDIENCE"], jwks=jwks)
        root = Path(config["ALPHA_PAPER_DATA_DIR"])
        if not root.is_absolute() or not root.is_dir() or root.is_symlink():
            raise RuntimeError("Persistent staging directory required")
        # Owner provisioning is server-only. Other identities cannot access
        # an account, even when their JWT is valid.
        import hashlib
        subject = config["ALPHA_AUTH0_OWNER_SUBJECT"]
        if not (1 <= len(subject) <= 255) or any(ord(c) < 33 or ord(c) > 126 for c in subject):
            raise ValueError("Invalid owner subject")
        owner = VerifiedPrincipal(
            "auth0_" + hashlib.sha256((verifier.issuer + "\0" + subject).encode()).hexdigest()[:48],
            verifier.issuer)
        accounts = PaperAccountService(root)
        try:
            accounts.open_account(owner, "primary")
        except Exception:
            accounts.close()
            raise
        return PaperStatusWSGI(verifier=verifier, accounts=accounts)
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise RuntimeError("Invalid Auth0 staging configuration") from exc


def create_app():
    return build_auth0_app(os.environ)
