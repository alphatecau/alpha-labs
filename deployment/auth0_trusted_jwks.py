"""Pinned Auth0 OIDC discovery/JWKS loader with HTTPS-only and bounded responses.

Network is isolated behind an injectable fetcher for deterministic testing.
"""
import json
import ssl
import urllib.parse
import urllib.request
from deployment.oidc_verifier import OIDCVerifier

def _https_json(url, *, max_bytes=131072):
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise PermissionError("invalid trusted HTTPS URL")
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args): raise PermissionError("redirect forbidden")
    opener=urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl.create_default_context()),NoRedirect())
    with opener.open(urllib.request.Request(url,headers={"Accept":"application/json"}),timeout=5) as response:
        if response.status!=200 or response.headers.get_content_type()!="application/json":
            raise PermissionError("invalid identity-provider response")
        data=response.read(max_bytes+1)
        if len(data)>max_bytes: raise PermissionError("identity-provider response too large")
        return json.loads(data)

def load_auth0_verifier(issuer,client_id,*,fetch=None):
    """Load a pinned issuer's JWKS. Refresh requires reloading, never accept URL from user."""
    if not isinstance(issuer,str) or not issuer.startswith("https://") or issuer.endswith("/"):
        raise ValueError("canonical HTTPS issuer required")
    p=urllib.parse.urlsplit(issuer)
    if not p.hostname or p.path or p.query or p.fragment or p.username or p.password:
        raise ValueError("issuer must be an origin")
    if not isinstance(client_id,str) or not client_id:
        raise ValueError("client ID required")
    fetch=fetch or _https_json
    metadata=fetch(issuer+"/.well-known/openid-configuration")
    if not isinstance(metadata,dict) or metadata.get("issuer")!=issuer+"/":
        raise PermissionError("issuer metadata mismatch")
    jwks_uri=metadata.get("jwks_uri")
    if jwks_uri!=issuer+"/.well-known/jwks.json":
        raise PermissionError("untrusted JWKS endpoint")
    keys=fetch(jwks_uri)
    if not isinstance(keys,dict) or not isinstance(keys.get("keys"),list) or not keys["keys"]:
        raise PermissionError("missing JWKS")
    return OIDCVerifier(issuer=issuer+"/",audience=client_id,jwks=keys)
