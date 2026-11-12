"""Bounded public HTTPS GETs with a caller-pinned origin and no redirects."""
import json
import math
import re
from time import monotonic
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class RejectPublicRedirects(HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise ValueError("public provider redirect refused")


def decode_public_json(data, *, parse_float=float):
    def unique_object(pairs):
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError("duplicate public JSON field")
        return result

    def invalid_constant(_):
        raise ValueError("non-finite public JSON number")

    return json.loads(data, object_pairs_hook=unique_object, parse_constant=invalid_constant,
                      parse_float=parse_float)


def read_public_https(url, *, origin, max_bytes, timeout, content_types=(), headers=None, opener=None):
    expected, actual = urlsplit(origin), urlsplit(url)
    if (expected.scheme != "https"
            or not re.fullmatch(r"(?:[a-z0-9-]+\.)+[a-z][a-z0-9-]*", expected.netloc)
            or expected.path or expected.query or expected.fragment
            or actual.scheme != "https" or actual.netloc.lower() != expected.netloc.lower()
            or actual.fragment or any(char.isspace() or ord(char) < 32 for char in url)):
        raise ValueError("pinned public HTTPS origin required")
    if (type(max_bytes) is not int or not 0 < max_bytes <= 16_000_000
            or type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 35):
        raise ValueError("bounded public request required")
    request_headers = {"User-Agent": "AlphaLabsResearch (read-only-public-data)", **(headers or {})}
    request_headers["Accept-Encoding"] = "identity"
    if content_types:
        request_headers["Accept"] = ", ".join(content_types)
    request = Request(url, method="GET", headers=request_headers)
    request_open = opener or build_opener(RejectPublicRedirects()).open
    deadline = monotonic() + timeout
    with request_open(request, timeout=timeout) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("unexpected provider response")
        types = response.headers.get_all("Content-Type", [])
        if content_types and (len(types) != 1 or types[0].split(";", 1)[0].strip().lower() not in content_types):
            raise ValueError("unexpected public provider content type")
        encoding = response.headers.get_all("Content-Encoding", [])
        transfer = response.headers.get_all("Transfer-Encoding", [])
        lengths = response.headers.get_all("Content-Length", [])
        if (encoding not in ([], ["identity"]) or transfer not in ([], ["chunked"])
                or (lengths and (transfer or len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,10}", lengths[0])))):
            raise ValueError("invalid public provider response framing")
        declared = int(lengths[0]) if lengths else None
        if declared is not None and declared > max_bytes:
            raise ValueError("public provider response exceeds limit")
        data = bytearray()
        read = getattr(response, "read1", response.read)
        while True:
            if monotonic() >= deadline:
                raise TimeoutError("public provider response deadline exceeded")
            chunk = read(min(65536, max_bytes + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > max_bytes:
                raise ValueError("public provider response exceeds limit")
        if monotonic() >= deadline:
            raise TimeoutError("public provider response deadline exceeded")
        if declared is not None and len(data) != declared:
            raise ValueError("incomplete public provider response")
    return bytes(data)
