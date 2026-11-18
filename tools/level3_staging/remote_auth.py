"""Offline remote-request authentication primitive; NOT an HTTP endpoint.

Signatures bind protocol, method, path, body digest, audience, nonce and expiry.
A durable nonce claim is REQUIRED by the caller before authorising any write.
"""
import base64
import hashlib
import json
import re
import time
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

class RemoteDenied(ValueError):
    pass

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")

def verify(envelope,body,public_key,audience,now=None):
    if not isinstance(envelope,dict) or set(envelope)!={"claims","signature"}:
        raise RemoteDenied("invalid envelope")
    claims=envelope["claims"]
    fields={"version","method","path","body_sha256","audience","nonce","expires_at"}
    if not isinstance(claims,dict) or set(claims)!=fields:
        raise RemoteDenied("invalid claims")
    clock=int(time.time() if now is None else now)
    if (claims["version"]!=1 or claims["method"]!="POST" or
        claims["path"]!="/v1/signed-create" or claims["audience"]!=audience or
        type(claims["expires_at"]) is not int or
        not clock < claims["expires_at"] <= clock+120 or
        not isinstance(claims["nonce"],str) or
        re.fullmatch(r"[a-f0-9]{64}",claims["nonce"]) is None):
        raise RemoteDenied("claim mismatch")
    if not isinstance(body,bytes) or len(body)>100000 or hashlib.sha256(body).hexdigest()!=claims["body_sha256"]:
        raise RemoteDenied("body digest mismatch")
    try:
        signature=base64.b64decode(envelope["signature"],validate=True)
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature,canonical(claims))
    except (InvalidSignature,ValueError,TypeError) as exc:
        raise RemoteDenied("signature invalid") from exc
    return claims["nonce"]
