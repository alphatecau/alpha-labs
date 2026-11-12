"""Fail-closed WSGI ingress boundary for authenticated research staging.

This adapter intentionally does not trust forwarded headers. It is suitable
for direct HTTPS WSGI test harnesses only. Render proxy support requires a
separate verified peer-trust adapter before authenticated deployment.
"""
from urllib.parse import urlsplit


class StrictDirectHTTPSIngress:
    def __init__(self, application, origin):
        parsed = urlsplit(origin)
        if (not callable(application) or parsed.scheme != "https"
                or not parsed.hostname or parsed.username or parsed.password
                or parsed.path or parsed.query or parsed.fragment):
            raise ValueError("trusted application and exact HTTPS origin required")
        self.application = application
        self.host = parsed.netloc.lower()

    def __call__(self, environ, start_response):
        forbidden = ("HTTP_FORWARDED", "HTTP_X_FORWARDED_PROTO",
                     "HTTP_X_FORWARDED_HOST", "HTTP_X_FORWARDED_FOR",
                     "HTTP_X_REAL_IP", "HTTP_X_FORWARDED_PORT")
        if (environ.get("wsgi.url_scheme") != "https"
                or environ.get("HTTP_HOST", "").lower() != self.host
                or any(key in environ for key in forbidden)):
            body = b'{"error":"untrusted_ingress"}'
            start_response("403 Forbidden", [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
                ("X-Content-Type-Options", "nosniff"),
            ])
            return [body]
        return self.application(environ, start_response)
