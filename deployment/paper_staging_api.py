"""Read-only, authenticated staging health API. Never exposes order submission.

No broker SDK, wallet signing, market feed or paper execution endpoints.
"""
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            return self.reply(200, {"service":"alpha-labs-paper-staging","mode":"RESEARCH_ONLY",
                                    "paper_execution":"DISABLED","live_execution":"DISABLED"})
        expected = os.environ.get("ALPHA_STAGING_READ_TOKEN", "")
        supplied = self.headers.get("Authorization", "")
        if not expected or len(expected) < 32 or not hmac.compare_digest(supplied, "Bearer "+expected):
            return self.reply(401, {"error":"unauthorised"})
        if self.path != "/api/v1/paper/status":
            return self.reply(404, {"error":"not found"})
        return self.reply(200, {"mode":"RESEARCH_ONLY","paper_execution":"DISABLED",
                                "live_execution":"DISABLED","risk_gate":"HALT",
                                "market_data":"UNAVAILABLE","ledger":"UNAVAILABLE"})
    def do_POST(self):
        return self.reply(405, {"error":"write methods disabled"})
    def do_PUT(self):
        return self.do_POST()
    def do_PATCH(self):
        return self.do_POST()
    def do_DELETE(self):
        return self.do_POST()
    def reply(self, status, body):
        raw=json.dumps(body, separators=(",",":")).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def log_message(self, format, *args):
        return

if __name__ == "__main__":
    port=int(os.environ.get("PORT","10000"))
    ThreadingHTTPServer(("0.0.0.0",port),Handler).serve_forever()
