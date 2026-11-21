"""Loopback-only authenticated MCP proposal bridge. Never expose directly to Internet.

The external TLS/authenticated tunnel is a separate deployment requirement.
Only the proposal-only JSON-RPC dispatcher is reachable. No local apply endpoint.
"""
import argparse
import hmac
import json
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .proposal_only_mcp import dispatch

MAX_REQUEST = 65536


def handler_for(root, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            # Never log credentials, proposal contents, or request bodies.
            pass

        def respond(self, status, body=b"", content_type="application/json"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/healthz":
                self.respond(200, b"live", "text/plain")
            else:
                self.respond(404)

        def do_POST(self):
            if self.path != "/mcp":
                self.respond(404)
                return
            auth = self.headers.get("Authorization", "")
            expected = "Bearer " + token
            if not hmac.compare_digest(auth.encode("utf-8"), expected.encode("utf-8")):
                self.respond(401)
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                self.respond(415)
                return
            try:
                size = int(self.headers.get("Content-Length", "-1"))
            except ValueError:
                self.respond(400)
                return
            if size < 1 or size > MAX_REQUEST or self.headers.get("Transfer-Encoding"):
                self.respond(413)
                return
            try:
                message = json.loads(self.rfile.read(size))
            except (ValueError, UnicodeError):
                self.respond(400)
                return
            if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
                self.respond(400)
                return
            if "id" not in message:
                self.respond(202)
                return
            response = dispatch(message, root)
            if response is None:
                self.respond(400)
                return
            body = json.dumps(response, separators=(",", ":")).encode("utf-8")
            self.respond(200, body)
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--port", type=int, default=8083)
    args = parser.parse_args()
    root = Path(args.root).resolve(strict=True)
    if not root.is_dir() or not 1024 <= args.port <= 65535:
        raise SystemExit("invalid workspace or port")
    token = os.environ.get("ALPHA_LEVEL3_MCP_TOKEN", "")
    if len(token) < 32:
        raise SystemExit("ALPHA_LEVEL3_MCP_TOKEN must contain at least 32 characters")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(root, token))
    server.daemon_threads = True
    server.serve_forever()


if __name__ == "__main__":
    main()
