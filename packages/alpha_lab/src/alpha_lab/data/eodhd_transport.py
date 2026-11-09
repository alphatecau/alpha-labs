"""Hardened, opt-in EODHD HTTPS transport. No default network invocation.

The transport is not wired to agents, scheduling, execution or the MCP server.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPError, HTTPRedirectHandler, Request, build_opener
from urllib.error import URLError

from alpha_lab.data.eodhd_client import ProviderReply

HOST = "eodhd.com"
MAX_RESPONSE_BYTES = 2_000_000
TIMEOUT_SECONDS = 8


class TransportError(RuntimeError):
    """Credential-safe transport error with no request URL or response body."""


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def https_transport(path: str, params: dict[str, str], *, opener=None) -> ProviderReply:
    """Make one bounded HTTPS request to an allowlisted provider.

    This function is not called automatically. The caller must separately
    authorise research and supply a credential. Tests inject a fake opener.
    """
    if not isinstance(path, str) or not path.startswith("/api/eod/"):
        raise TransportError("Unsupported provider endpoint")
    symbol = path.removeprefix("/api/eod/")
    if not symbol or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for c in symbol) or len(symbol) > 40:
        raise TransportError("Invalid endpoint symbol")
    if not isinstance(params, dict) or set(params) != {"api_token", "from", "to", "fmt"}:
        raise TransportError("Invalid request parameters")
    if params.get("fmt") != "json" or not all(isinstance(v, str) for v in params.values()):
        raise TransportError("Invalid request parameters")
    url = "https://" + HOST + path + "?" + urlencode(params)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != HOST or parsed.port is not None:
        raise TransportError("Untrusted provider host")
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "AlphaLabs-Research/0.1"}, method="GET")
    client = opener if opener is not None else build_opener(_NoRedirects())
    try:
        with client.open(req, timeout=TIMEOUT_SECONDS) as response:
            status = response.status
            if status != 200:
                return ProviderReply(status, "")
            data = response.read(MAX_RESPONSE_BYTES + 1)
            if len(data) > MAX_RESPONSE_BYTES:
                raise TransportError("Provider response too large")
            try:
                body = data.decode("utf-8")
            except UnicodeDecodeError:
                raise TransportError("Invalid response encoding") from None
            return ProviderReply(status, body)
    except HTTPError as exc:
        return ProviderReply(exc.code, "")
    except TransportError:
        raise
    except (URLError, TimeoutError, OSError, ValueError):
        raise TransportError("Provider transport unavailable") from None
