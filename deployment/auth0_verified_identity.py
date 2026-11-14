"""Auth0 ID-token verification for isolated research-only staging.

This verifier does NOT accept caller-supplied identity claims as proof.
The trusted callback must supply the nonce from its single-use, server-side
PKCE/state transaction. Never use a browser-provided nonce as expected_nonce.
"""
import base64
import json
import time
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa

from alpha_lab.research.paper_account_service import VerifiedPrincipal


def _decode(segment):
    if not isinstance(segment, str) or len(segment) > 16384:
        raise PermissionError("invalid JWT encoding")
    try:
        return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
    except (ValueError, TypeError) as exc:
        raise PermissionError("invalid JWT encoding") from exc


class Auth0IDTokenVerifier:
    def __init__(self, *, issuer, client_id, jwks, clock=time.time):
        parsed = urlsplit(issuer)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
                parsed.password or parsed.port not in (None, 443) or
                parsed.query or parsed.fragment or parsed.path not in ("", "/")):
            raise ValueError("invalid Auth0 issuer")
        if not isinstance(client_id, str) or not client_id:
            raise ValueError("client ID required")
        if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
            raise ValueError("trusted JWKS required")
        self.issuer = issuer.rstrip("/") + "/"
        self.client_id = client_id
        self.jwks = jwks
        self.clock = clock

    def verify(self, token, *, expected_nonce):
        if not isinstance(expected_nonce, str) or len(expected_nonce) < 16:
            raise PermissionError("server-bound nonce required")
        if not isinstance(token, str) or len(token) > 16384:
            raise PermissionError("invalid token")
        parts = token.split(".")
        if len(parts) != 3:
            raise PermissionError("invalid token")
        try:
            header = json.loads(_decode(parts[0]))
            claims = json.loads(_decode(parts[1]))
        except (ValueError, UnicodeDecodeError, TypeError) as exc:
            raise PermissionError("invalid token") from exc
        if not isinstance(header, dict) or not isinstance(claims, dict):
            raise PermissionError("invalid token")
        if header.get("alg") != "RS256" or header.get("typ", "JWT") != "JWT":
            raise PermissionError("unsupported signing algorithm")
        matches = [key for key in self.jwks["keys"] if (
            isinstance(key, dict) and key.get("kid") == header.get("kid")
            and key.get("kty") == "RSA" and key.get("use", "sig") == "sig"
            and key.get("alg", "RS256") == "RS256"
        )]
        if len(matches) != 1:
            raise PermissionError("unknown signing key")
        key = matches[0]
        try:
            n = int.from_bytes(_decode(key["n"]), "big")
            e = int.from_bytes(_decode(key["e"]), "big")
            public = rsa.RSAPublicNumbers(e, n).public_key()
            public.verify(_decode(parts[2]), (parts[0] + "." + parts[1]).encode(),
                          padding.PKCS1v15(), hashes.SHA256())
        except (InvalidSignature, ValueError, TypeError, KeyError) as exc:
            raise PermissionError("invalid signature") from exc
        now = int(self.clock())
        aud = claims.get("aud")
        valid_audience = aud == self.client_id or (
            isinstance(aud, list) and self.client_id in aud and all(isinstance(a, str) for a in aud)
        )
        if (claims.get("iss") != self.issuer or not valid_audience or
                claims.get("nonce") != expected_nonce or
                type(claims.get("exp")) is not int or claims["exp"] <= now or
                type(claims.get("iat")) is not int or claims["iat"] > now + 60 or
                claims["iat"] < now - 86400 or
                not isinstance(claims.get("sub"), str) or not claims["sub"]):
            raise PermissionError("invalid ID-token claims")
        nbf = claims.get("nbf")
        if nbf is not None and (type(nbf) is not int or nbf > now):
            raise PermissionError("ID token not yet valid")
        if isinstance(aud, list) and len(aud) > 1 and claims.get("azp") != self.client_id:
            raise PermissionError("invalid authorised party")
        return VerifiedPrincipal(subject=claims["sub"], issuer=self.issuer)
