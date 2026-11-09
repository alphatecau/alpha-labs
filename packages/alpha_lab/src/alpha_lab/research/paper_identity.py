"""Offline testable HMAC identity verifier for trusted paper-service adapters.

Research-only example: production should use an established identity provider
with pinned issuer/audience, revocation, key rotation and secure transport.
Never put signing keys in client code or source control.
"""
import base64
import hashlib
import hmac
import json
import re
from datetime import datetime, timezone

from alpha_lab.research.paper_account_service import VerifiedPrincipal


def _encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise PermissionError("Invalid token encoding")
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class PaperIdentityVerifier:
    def __init__(self, *, key, issuer, audience):
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError("Signing key must be at least 32 bytes")
        if not isinstance(issuer, str) or not issuer or not isinstance(audience, str) or not audience:
            raise ValueError("Issuer and audience required")
        self._key = key
        self._issuer = issuer
        self._audience = audience

    def verify(self, token, *, now: datetime):
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset().total_seconds() != 0:
            raise ValueError("UTC verification time required")
        if not isinstance(token, str) or len(token) > 4096:
            raise PermissionError("Invalid identity token")
        parts = token.split(".")
        if len(parts) != 2:
            raise PermissionError("Invalid identity token")
        payload_segment, signature_segment = parts
        try:
            encoded_payload = payload_segment.encode("ascii")
        except UnicodeEncodeError as exc:
            raise PermissionError("Invalid identity token encoding") from exc
        expected = hmac.new(self._key, encoded_payload, hashlib.sha256).digest()
        try:
            signature = _decode(signature_segment)
            raw = _decode(payload_segment)
        except (ValueError, UnicodeError) as exc:
            raise PermissionError("Invalid identity token") from exc
        if not hmac.compare_digest(signature, expected):
            raise PermissionError("Invalid token signature")
        try:
            claims = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise PermissionError("Invalid identity claims") from exc
        if not isinstance(claims, dict) or set(claims) != {"sub", "iss", "aud", "exp", "iat"}:
            raise PermissionError("Unexpected identity claims")
        if claims["iss"] != self._issuer or claims["aud"] != self._audience:
            raise PermissionError("Identity issuer or audience mismatch")
        if not isinstance(claims["sub"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", claims["sub"]):
            raise PermissionError("Invalid subject")
        if type(claims["exp"]) is not int or type(claims["iat"]) is not int:
            raise PermissionError("Invalid token times")
        timestamp = int(now.timestamp())
        if claims["iat"] > timestamp or claims["exp"] <= timestamp or claims["exp"] <= claims["iat"]:
            raise PermissionError("Expired or not-yet-valid identity")
        if claims["exp"] - claims["iat"] > 900:
            raise PermissionError("Excessive token lifetime")
        return VerifiedPrincipal(subject=claims["sub"], issuer=self._issuer)


def issue_test_token(key, claims):
    """For offline deterministic tests only; not a public authentication API."""
    payload = _encode(json.dumps(claims, sort_keys=True, separators=(",", ":")).encode())
    signature = hmac.new(key, payload.encode("ascii"), hashlib.sha256).digest()
    return payload + "." + _encode(signature)
