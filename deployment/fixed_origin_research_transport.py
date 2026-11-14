"""Fixed-origin HTTPS transport for trusted research relay.

Only for server-side BFF use. Browser-controlled URL, redirects, cookies,
Authorization, and TLS verification overrides are not accepted.
"""
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("backend redirect rejected")


class FixedOriginResearchTransport:
    def __init__(self, origin, *, timeout=5.0):
        parsed = urllib.parse.urlsplit(origin)
        if (parsed.scheme != "https" or not parsed.hostname or
                parsed.username is not None or parsed.password is not None or
                parsed.path not in ("", "/") or parsed.query or parsed.fragment or
                not 0 < timeout <= 15):
            raise ValueError("fixed HTTPS origin and bounded timeout required")
        self._origin = origin.rstrip("/")
        self._timeout = timeout
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
            _RejectRedirects(),
        )

    def __call__(self, path, headers):
        if path not in ("/api/v1/research/runs", "/api/v1/research/summary"):
            raise PermissionError("unsupported backend resource")
        if (not isinstance(headers, dict) or
                set(headers) != {"Authorization", "Accept"} or
                headers["Accept"] != "application/json" or
                not isinstance(headers["Authorization"], str) or
                not headers["Authorization"].startswith("Bearer ") or
                len(headers["Authorization"]) > 4096):
            raise PermissionError("invalid backend request headers")
        request = urllib.request.Request(
            self._origin + path,
            headers={"Authorization": headers["Authorization"], "Accept": "application/json"},
            method="GET",
        )
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                if response.status != 200:
                    raise RuntimeError("backend unavailable")
                if response.headers.get_content_type() != "application/json":
                    raise RuntimeError("unexpected backend content type")
                raw = response.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    raise RuntimeError("backend response too large")
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise RuntimeError("invalid backend response")
                return result
        except (urllib.error.URLError, ValueError, UnicodeError) as exc:
            raise RuntimeError("backend unavailable") from exc
