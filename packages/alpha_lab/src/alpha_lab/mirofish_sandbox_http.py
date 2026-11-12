"""Strict loopback-only HTTP client for MiroFish asynchronous API lifecycle."""
import http.client
import ipaddress
import json
from urllib.parse import urlsplit
from .simulation_adapter import SimulationAdapterError

class MiroFishSandboxHTTP:
    def __init__(self, base_url: str, *, timeout_seconds: float = 5,
                 max_response_bytes: int = 100_000):
        parsed = urlsplit(base_url)
        try:
            host = ipaddress.ip_address(parsed.hostname or "")
            port = parsed.port
        except (ValueError, TypeError) as exc:
            raise SimulationAdapterError("Explicit loopback IPv4 host and port required") from exc
        if (parsed.scheme != "http" or host.version != 4 or not host.is_loopback
                or not port or parsed.path not in ("", "/") or parsed.query
                or parsed.fragment or parsed.username or parsed.password):
            raise SimulationAdapterError("Sandbox transport must use loopback IPv4")
        if not 0 < timeout_seconds <= 10 or not 1 <= max_response_bytes <= 100_000:
            raise SimulationAdapterError("Invalid request limits")
        self.host, self.port = str(host), port
        self.timeout, self.max_response_bytes = timeout_seconds, max_response_bytes

    def __call__(self, method: str, path: str, payload: dict | None) -> dict:
        if method not in ("GET", "POST") or not path.startswith("/api/") or (
            any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/_-" for c in path)
        ):
            raise SimulationAdapterError("Unsupported API path or method")
        body = None if method == "GET" else json.dumps(
            payload or {}, allow_nan=False, separators=(",", ":")).encode()
        if body is not None and len(body) > 16384:
            raise SimulationAdapterError("Request too large")
        conn = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        try:
            conn.request(method, path, body=body, headers={
                "Accept": "application/json", "Connection": "close",
                "Content-Type": "application/json"})
            response = conn.getresponse()
            if response.status != 200:
                raise SimulationAdapterError("MiroFish API returned non-200")
            if response.getheader("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                raise SimulationAdapterError("Unexpected response type")
            data = response.read(self.max_response_bytes + 1)
            if len(data) > self.max_response_bytes:
                raise SimulationAdapterError("Response too large")
            result = json.loads(data)
            if not isinstance(result, dict):
                raise SimulationAdapterError("Invalid API response")
            return result
        except (OSError, TimeoutError, http.client.HTTPException, ValueError) as exc:
            raise SimulationAdapterError("MiroFish sandbox API unavailable or invalid") from exc
        finally:
            conn.close()
