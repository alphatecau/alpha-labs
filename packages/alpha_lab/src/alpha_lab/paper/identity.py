"""Local operator tokens only. Production registration/MFA/passkeys are absent."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from .contracts import Forbidden, Principal


@dataclass(frozen=True)
class TokenRecord:
    principal: Principal
    expires_at: datetime


class LocalIdentity:
    def __init__(self):
        self._tokens: dict[str, TokenRecord] = {}

    def issue(self, principal: Principal, *, lifetime_seconds=3600) -> str:
        if type(lifetime_seconds) is not int or not 1 <= lifetime_seconds <= 86400:
            raise ValueError("invalid token lifetime")
        token = secrets.token_urlsafe(32)
        self._tokens[self._hash(token)] = TokenRecord(
            principal, datetime.now(timezone.utc) + timedelta(seconds=lifetime_seconds))
        return token

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def authenticate(self, token: str, *, now: datetime | None = None) -> Principal:
        if type(token) is not str or not 40 <= len(token) <= 100:
            raise Forbidden("invalid or expired credentials")
        record = self._tokens.get(self._hash(token))
        now = now or datetime.now(timezone.utc)
        if record is None or record.expires_at <= now:
            raise Forbidden("invalid or expired credentials")
        return record.principal

    def revoke(self, token: str):
        self._tokens.pop(self._hash(token), None)
