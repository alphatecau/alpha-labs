"""Strict OIDC RS256 ID-token verifier with pinned trusted JWKS.

JWKS must be fetched server-side from the issuer's verified discovery endpoint
using HTTPS, bounded cache and refresh. No network access is performed here.
"""
import base64
import hashlib
import json
import re
import time
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes

def decode_part(part):
    if not isinstance(part,str) or not re.fullmatch(r"[A-Za-z0-9_-]+",part):
        raise PermissionError("invalid token encoding")
    return base64.urlsafe_b64decode(part + "=" * (-len(part)%4))

class OIDCVerifier:
    def __init__(self, *, issuer, audience, jwks, clock=None):
        if not isinstance(issuer,str) or not issuer.startswith("https://") or issuer.endswith("/"):
            raise ValueError("HTTPS issuer required")
        if not isinstance(audience,str) or not audience:
            raise ValueError("audience required")
        if not isinstance(jwks,dict) or not isinstance(jwks.get("keys"),list):
            raise ValueError("trusted JWKS required")
        self.issuer,self.audience,self.jwks=issuer,audience,jwks
        self.clock=clock or time.time

    def __call__(self, credential):
        try:
            if not isinstance(credential,str) or len(credential)>8192:
                raise ValueError()
            parts=credential.split(".")
            if len(parts)!=3: raise ValueError()
            header=json.loads(decode_part(parts[0]))
            claims=json.loads(decode_part(parts[1]))
            if not isinstance(header,dict) or not isinstance(claims,dict):
                raise ValueError()
            if header.get("alg")!="RS256" or header.get("typ") not in (None,"JWT") or not isinstance(header.get("kid"),str):
                raise ValueError()
            keys=[k for k in self.jwks["keys"] if k.get("kid")==header["kid"] and k.get("kty")=="RSA" and k.get("use","sig")=="sig" and k.get("alg","RS256")=="RS256"]
            if len(keys)!=1: raise ValueError()
            k=keys[0]
            n=int.from_bytes(decode_part(k["n"]),"big")
            e=int.from_bytes(decode_part(k["e"]),"big")
            if n.bit_length()<2048 or e!=65537: raise ValueError()
            key=rsa.RSAPublicNumbers(e,n).public_key()
            key.verify(decode_part(parts[2]),(parts[0]+"."+parts[1]).encode(),padding.PKCS1v15(),hashes.SHA256())
            now=int(self.clock())
            if claims.get("iss")!=self.issuer: raise ValueError()
            aud=claims.get("aud")
            if not (aud==self.audience or isinstance(aud,list) and self.audience in aud):
                raise ValueError()
            if isinstance(aud,list) and len(aud)>1 and claims.get("azp")!=self.audience:
                raise ValueError()
            if type(claims.get("exp")) is not int or type(claims.get("iat")) is not int: raise ValueError()
            if not (now<claims["exp"]<=now+3600 and now-3600<=claims["iat"]<=now+30): raise ValueError()
            if "nbf" in claims and (type(claims["nbf"]) is not int or claims["nbf"]>now+30): raise ValueError()
            sub=claims.get("sub")
            if not isinstance(sub,str) or not 1<=len(sub)<=255: raise ValueError()
            # Identity scoped to issuer. Deterministic, not browser-controlled.
            owner="oidc_"+hashlib.sha256((self.issuer+"\x00"+sub).encode()).hexdigest()
            return {"verified":True,"owner_id":owner,"issuer":self.issuer}
        except Exception as exc:
            raise PermissionError("invalid OIDC token") from exc
