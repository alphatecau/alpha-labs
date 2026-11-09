"""Offline, pinned-JWKS Auth0 RS256 verifier for research-only staging.

No network access or dynamic key fetch. Rotation requires a reviewed configuration
update. JWT bearer tokens are not login sessions; no callback/logout endpoints here.
"""
import base64
import hashlib
import json
import re
from datetime import datetime, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import hashes

from alpha_lab.research.paper_account_service import VerifiedPrincipal


def _decode(part):
    if not isinstance(part, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", part):
        raise PermissionError("Malformed JWT")
    try:
        return base64.b64decode(part + "=" * (-len(part) % 4), altchars=b"-_", validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise PermissionError("Malformed JWT") from exc


def _object(part):
    try:
        obj = json.loads(_decode(part))
    except (ValueError, UnicodeError) as exc:
        raise PermissionError("Malformed JWT JSON") from exc
    if not isinstance(obj, dict):
        raise PermissionError("JWT object required")
    return obj


class Auth0JWTVerifier:
    """Validate access JWTs against explicitly pinned Auth0 RSA public keys."""
    _auth0_verified_bearer = True

    def __init__(self, *, issuer, audience, jwks):
        if not isinstance(issuer, str) or not re.fullmatch(r"https://[A-Za-z0-9.-]+/", issuer):
            raise ValueError("HTTPS issuer with trailing slash required")
        if not isinstance(audience, str) or not audience:
            raise ValueError("API audience required")
        if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list) or not jwks["keys"]:
            raise ValueError("Pinned JWKS required")
        self.issuer, self.audience = issuer, audience
        self.keys = {}
        for item in jwks["keys"]:
            if not isinstance(item, dict) or item.get("kty") != "RSA" or item.get("alg", "RS256") != "RS256" or item.get("use", "sig") != "sig":
                raise ValueError("Invalid JWKS key")
            kid = item.get("kid")
            if not isinstance(kid, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", kid) or kid in self.keys:
                raise ValueError("Missing or duplicate key ID")
            try:
                n = int.from_bytes(_decode(item["n"]), "big")
                e = int.from_bytes(_decode(item["e"]), "big")
                if n.bit_length() < 2048 or e != 65537:
                    raise ValueError("Unsafe RSA key")
                self.keys[kid] = rsa.RSAPublicNumbers(e, n).public_key()
            except (KeyError, ValueError, TypeError) as exc:
                raise ValueError("Invalid RSA public key") from exc

    def verify(self, token, *, now):
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset().total_seconds() != 0:
            raise ValueError("UTC verification time required")
        if not isinstance(token, str) or len(token) > 8192:
            raise PermissionError("Invalid JWT")
        parts = token.split(".")
        if len(parts) != 3:
            raise PermissionError("JWT requires three segments")
        header = _object(parts[0])
        if header.get("alg") != "RS256" or header.get("typ", "JWT") != "JWT" or set(header) - {"alg", "typ", "kid"}:
            raise PermissionError("Unsupported JWT header")
        key = self.keys.get(header.get("kid")) if isinstance(header.get("kid"), str) else None
        if key is None:
            raise PermissionError("Unknown signing key")
        try:
            key.verify(_decode(parts[2]), (parts[0] + "." + parts[1]).encode("ascii"),
                       padding.PKCS1v15(), hashes.SHA256())
        except (InvalidSignature, ValueError, UnicodeError) as exc:
            raise PermissionError("Invalid JWT signature") from exc
        claims = _object(parts[1])
        timestamp = int(now.timestamp())
        if claims.get("iss") != self.issuer:
            raise PermissionError("Invalid issuer")
        aud = claims.get("aud")
        if not (aud == self.audience or isinstance(aud, list) and self.audience in aud and all(isinstance(x, str) for x in aud)):
            raise PermissionError("Invalid audience")
        if type(claims.get("exp")) is not int or claims["exp"] <= timestamp:
            raise PermissionError("Expired token")
        if type(claims.get("iat")) is not int or claims["iat"] > timestamp + 60 or claims["exp"] <= claims["iat"]:
            raise PermissionError("Invalid issued-at")
        if "nbf" in claims and (type(claims["nbf"]) is not int or claims["nbf"] > timestamp):
            raise PermissionError("Not yet valid")
        sub = claims.get("sub")
        if not isinstance(sub, str) or not (1 <= len(sub) <= 255) or any(ord(c) < 33 or ord(c) > 126 for c in sub):
            raise PermissionError("Invalid subject")
        # The account service only accepts safe opaque identifiers. Bind both
        # verified issuer and provider subject to prevent tenant collisions.
        safe_subject = "auth0_" + hashlib.sha256((self.issuer + "\0" + sub).encode()).hexdigest()[:48]
        return VerifiedPrincipal(subject=safe_subject, issuer=self.issuer)
