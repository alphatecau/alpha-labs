"""Bounded public HTTPS GETs with a caller-pinned origin and no redirects."""
import math
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class RejectPublicRedirects(HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise ValueError("public provider redirect refused")


def read_public_https(url, *, origin, max_bytes, timeout):
    expected, actual = urlsplit(origin), urlsplit(url)
    if (expected.scheme != "https" or not expected.hostname or expected.username or expected.password
            or expected.path or expected.query or expected.fragment
            or actual.scheme != "https" or actual.netloc.lower() != expected.netloc.lower()
            or actual.username or actual.password or actual.fragment):
        raise ValueError("pinned public HTTPS origin required")
    if (type(max_bytes) is not int or not 0 < max_bytes <= 16_000_000
            or type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 35):
        raise ValueError("bounded public request required")
    request = Request(url, method="GET", headers={"User-Agent": "AlphaLabsResearch (read-only-public-data)"})
    opener = build_opener(RejectPublicRedirects())
    with opener.open(request, timeout=timeout) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("unexpected public provider response")
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("public provider response exceeds limit")
    return data
