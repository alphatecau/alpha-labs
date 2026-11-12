"""Trusted-server paper account registry (research prototype; not an HTTP service).

Caller identity MUST be authenticated upstream. Never accept a client-supplied
user ID as authentication. Does not manage broker credentials or live orders.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re

from alpha_lab.research.guarded_paper_runtime import GuardedPaperRuntime
from alpha_lab.research.paper_first_authority import TradingAuthority


@dataclass(frozen=True)
class VerifiedPrincipal:
    """Created only by trusted authentication middleware, never from request JSON."""
    subject: str
    issuer: str


class PaperAccountService:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("Invalid account storage directory")
        self._sessions = {}

    def _require(self, principal: VerifiedPrincipal, account: str):
        if not isinstance(principal, VerifiedPrincipal):
            raise PermissionError("Authentication required")
        if not isinstance(principal.subject, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", principal.subject):
            raise PermissionError("Invalid authenticated subject")
        if not isinstance(principal.issuer, str) or not principal.issuer.strip():
            raise PermissionError("Invalid authentication issuer")
        if not isinstance(account, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", account):
            raise PermissionError("Invalid account identifier")
        return principal.issuer + ":" + principal.subject + ":" + account

    def open_account(self, principal: VerifiedPrincipal, account: str):
        """Trusted-server operation. New sessions default to HALT."""
        import hashlib
        key = self._require(principal, account)
        if key not in self._sessions:
            filename = hashlib.sha256(key.encode()).hexdigest() + ".sqlite3"
            session = GuardedPaperRuntime(self.root / filename)
            self._sessions[key] = session
        return {"mode": "PAPER", "account": account, **self._sessions[key].status()}

    def status(self, principal: VerifiedPrincipal, account: str):
        key = self._require(principal, account)
        if key not in self._sessions:
            raise PermissionError("Unknown or unopened account")
        return self._sessions[key].status()

    def enable_paper(self, principal: VerifiedPrincipal, account: str, *,
                     authority: TradingAuthority, operator_approved=False):
        key = self._require(principal, account)
        if key not in self._sessions:
            raise PermissionError("Unknown or unopened account")
        if not isinstance(authority, TradingAuthority):
            raise PermissionError("Authority must originate from trusted server policy")
        runtime = self._sessions[key]
        runtime.set_authority(authority)
        return runtime.enable(operator_approved=operator_approved)

    def close(self):
        for session in self._sessions.values():
            session.close()
        self._sessions.clear()
