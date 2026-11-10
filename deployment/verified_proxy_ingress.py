"""Opt-in trusted reverse-proxy boundary for research-only WSGI.

Do not enable on Render until the actual proxy-to-app socket peer range is
independently established. Never infer trust from X-Forwarded-For.
"""
import ipaddress
from urllib.parse import urlsplit


class VerifiedProxyIngress:
    def __init__(self, application, origin, *, trusted_peer_cidrs):
        p = urlsplit(origin)
        if (not callable(application) or p.scheme != "https" or not p.hostname
                or p.username or p.password or p.path or p.query or p.fragment
                or not trusted_peer_cidrs):
            raise ValueError("explicit trusted proxy and HTTPS origin required")
        self.application = application
        self.host = p.netloc.lower()
        self.networks = tuple(ipaddress.ip_network(v, strict=True)
                              for v in trusted_peer_cidrs)
        if any(n.prefixlen == 0 for n in self.networks):
            raise ValueError("unrestricted proxy CIDR forbidden")

    def __call__(self, environ, start_response):
        def deny():
            body = b'{"error":"untrusted_proxy"}'
            start_response("403 Forbidden", [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
                ("X-Content-Type-Options", "nosniff")])
            return [body]
        try:
            peer = ipaddress.ip_address(environ["REMOTE_ADDR"])
            if not any(peer in n for n in self.networks):
                return deny()
            # Only one proxy hop is accepted. Ambiguous or client-controlled
            # forwarding chains are rejected rather than heuristically parsed.
            if any(k in environ for k in ("HTTP_FORWARDED", "HTTP_X_FORWARDED_FOR",
                                          "HTTP_X_FORWARDED_HOST", "HTTP_X_REAL_IP",
                                          "HTTP_X_FORWARDED_PORT")):
                return deny()
            if (environ.get("HTTP_X_FORWARDED_PROTO") != "https"
                    or environ.get("HTTP_HOST", "").lower() != self.host):
                return deny()
            clean = dict(environ)
            for k in tuple(clean):
                if k.startswith("HTTP_X_FORWARDED_") or k == "HTTP_FORWARDED":
                    del clean[k]
            clean["wsgi.url_scheme"] = "https"
            clean["HTTPS"] = "on"
            return self.application(clean, start_response)
        except (KeyError, ValueError, TypeError):
            return deny()
