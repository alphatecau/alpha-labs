"""Loopback-only HTTP transport for an isolated MiroFish backend.

The upstream endpoint and request schema MUST be confirmed against a pinned
MiroFish revision before real execution. Default path is intentionally unset.
No credentials, public URLs, redirects, or broker access are supported.
"""
import http.client
import ipaddress
import json
from urllib.parse import urlsplit
from .simulation_adapter import SimulationAdapterError


class MiroFishLoopbackTransport:
    def __init__(self, endpoint: str, *, timeout_seconds: float = 5.0,
                 max_response_bytes: int = 100_000):
        parsed = urlsplit(endpoint)
        try:
            address = ipaddress.ip_address(parsed.hostname or "")
            port = parsed.port
        except (ValueError, TypeError) as exc:
            raise SimulationAdapterError("Explicit loopback IP and port required") from exc
        if (parsed.scheme != "http" or not address.is_loopback or
                address.version != 4 or parsed.username or parsed.password or
                parsed.query or parsed.fragment or not port or
                not parsed.path.startswith("/") or parsed.path.startswith("//")):
            raise SimulationAdapterError("Only an explicit IPv4 loopback HTTP endpoint is permitted")
        if not 0 < timeout_seconds <= 10 or not 1 <= max_response_bytes <= 100_000:
            raise SimulationAdapterError("Transport budget invalid")
        self.host = str(address)
        self.port = port
        self.path = parsed.path
        self.timeout = timeout_seconds
        self.max_response_bytes = max_response_bytes

    def __call__(self, request):
        body = json.dumps(request, allow_nan=False, separators=(",", ":")).encode()
        if len(body) > 16_384:
            raise SimulationAdapterError("Request exceeds size budget")
        conn = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        try:
            conn.request("POST", self.path, body=body, headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Connection": "close",
            })
            response = conn.getresponse()
            if response.status != 200:
                raise SimulationAdapterError("MiroFish backend returned non-success status")
            if response.getheader("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                raise SimulationAdapterError("Backend returned non-JSON content")
            payload = response.read(self.max_response_bytes + 1)
            if len(payload) > self.max_response_bytes:
                raise SimulationAdapterError("Backend response exceeds size budget")
            try:
                return json.loads(payload)
            except (UnicodeError, ValueError) as exc:
                raise SimulationAdapterError("Invalid JSON response") from exc
        except (OSError, TimeoutError, http.client.HTTPException) as exc:
            raise SimulationAdapterError("MiroFish loopback transport unavailable") from exc
        finally:
            conn.close()
