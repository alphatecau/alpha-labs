"""Fail-closed staging application factory: read-only, no order endpoints.

Requires server-owned configuration and an existing writable data directory.
Never import this module as proof of production authentication readiness.
"""
import base64
import os
from pathlib import Path

from alpha_lab.research.paper_account_service import PaperAccountService, VerifiedPrincipal
from alpha_lab.research.paper_identity import PaperIdentityVerifier
from alpha_lab.research.paper_status_wsgi import PaperStatusWSGI


def build_app(config):
    required = ("ALPHA_PAPER_SIGNING_KEY_B64", "ALPHA_PAPER_ISSUER",
                "ALPHA_PAPER_AUDIENCE", "ALPHA_PAPER_DATA_DIR",
                "ALPHA_PAPER_OWNER_SUBJECT")
    if any(not isinstance(config.get(name), str) or not config[name] for name in required):
        raise RuntimeError("Staging configuration incomplete; refusing to start")
    try:
        key = base64.b64decode(config["ALPHA_PAPER_SIGNING_KEY_B64"], validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise RuntimeError("Invalid signing key encoding") from exc
    if len(key) < 32:
        raise RuntimeError("Weak signing key; refusing to start")
    root = Path(config["ALPHA_PAPER_DATA_DIR"])
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise RuntimeError("Persistent data directory must exist and be absolute")
    verifier = PaperIdentityVerifier(
        key=key, issuer=config["ALPHA_PAPER_ISSUER"],
        audience=config["ALPHA_PAPER_AUDIENCE"])
    accounts = PaperAccountService(root)
    try:
        owner = VerifiedPrincipal(config["ALPHA_PAPER_OWNER_SUBJECT"],
                                  config["ALPHA_PAPER_ISSUER"])
        accounts.open_account(owner, "primary")
    except Exception:
        accounts.close()
        raise
    return PaperStatusWSGI(verifier=verifier, accounts=accounts)


def create_app():
    return build_app(os.environ)


# WSGI server loads this attribute. Missing secrets or data storage fail startup.
app = None


def get_app():
    return create_app()
