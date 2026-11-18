#!/usr/bin/env python3
"""Read-only loopback probe for manually controlled MCP reconnection."""
import argparse
import urllib.request
import urllib.error

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", default="http://127.0.0.1:8080")
    args = parser.parse_args()
    if args.origin != "http://127.0.0.1:8080":
        parser.error("Only the local loopback tunnel endpoint is permitted")
    for path, expected in (("/healthz", "live"), ("/readyz", "ready")):
        try:
            with urllib.request.urlopen(args.origin + path, timeout=5) as response:
                body = response.read(256).decode("utf-8", "replace").strip()
                if response.status != 200 or body != expected:
                    raise RuntimeError(f"{path}: unexpected response")
            print(f"{path}: PASS")
        except (OSError, RuntimeError) as exc:
            print(f"{path}: FAIL ({type(exc).__name__})")
            return 1
    print("Loopback checks PASS; independently verify ChatGPT workspace_status.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
