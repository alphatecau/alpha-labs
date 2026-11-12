"""Minimal isolated staging probe. No authentication, sessions, trading or databases.

This application is intentionally not a functional Alpha Labs platform.
"""
import json
import os


def application(environ, start_response):
    path = environ.get("PATH_INFO", "")
    method = environ.get("REQUEST_METHOD", "")
    if path == "/healthz" and method == "GET":
        body = json.dumps({"status": "ok", "mode": "research_only", "trading": "disabled"}).encode()
        status = "200 OK"
    else:
        body = b'{"error":"unavailable"}'
        status = "404 Not Found"
    start_response(status, [
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
        ("X-Content-Type-Options", "nosniff"),
    ])
    return [body]


if __name__ == "__main__":
    from wsgiref.simple_server import make_server
    port = int(os.environ.get("PORT", "10000"))
    with make_server(os.environ.get("HOST", "127.0.0.1"), port, application) as server:
        server.serve_forever()
