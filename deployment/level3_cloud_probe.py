"""Read-only cloud deployment probe. Never exposes signed-write operations."""
import json
import os
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/healthz","/readyz"):
            self.send_error(404)
            return
        if self.path=="/healthz":
            status,body=200,{"service":"alpha-labs-level3-broker-probe","alive":True}
        else:
            status,body=503,{"service":"alpha-labs-level3-broker-probe","ready":False,
                             "reason":"independent durable custody and audit anchor not configured"}
        payload=json.dumps(body,separators=(",",":")).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Length",str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
    def do_POST(self):
        self.send_error(405,"signed writes unavailable")
    def log_message(self,format,*args):
        pass

def main():
    port=int(os.environ.get("PORT","10000"))
    # Only the hosted read-only probe listens on Render's ingress interface.
    host = "0.0.0.0" if os.environ.get("RENDER") == "true" else "127.0.0.1"  # nosec B104
    ThreadingHTTPServer((host,port),Handler).serve_forever()

if __name__=="__main__":
    main()
