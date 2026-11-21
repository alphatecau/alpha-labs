# MCP3 authenticated loopback bridge — staging, not remotely activated

This bridge is an **independent** HTTP server bound only to `127.0.0.1:8083`, leaving the existing Level 2 tunnel on port 8080 unchanged. It exposes `POST /mcp` for the proposal-only MCP dispatcher. It requires `Authorization: Bearer <token>`, with the token supplied from `ALPHA_LEVEL3_MCP_TOKEN` (minimum 32 characters). It does **not** expose approve, apply, shell, general file writes, or a remote network listener.

The local `GET /healthz` response does not authenticate. It reports only process liveness.

## Offline verification

```sh
python -m unittest discover -s tests -p 'test_level3_loopback_bridge.py' -v
python -m unittest discover -s tests -p 'test_level3_*.py' -q
```

## Security gates before external connection

1. Perform an independent review of this implementation, including concurrency, request timeouts, authentication, input validation, replay/resource limits, and same-UID filesystem threats.
2. Configure a **separate** authenticated TLS-capable tunnel profile and endpoint for MCP3. Do not reuse, replace or modify the working Level 2 tunnel profile.
3. Verify tunnel ingress identity, audience, scope and HTTPS transport; do not forward an unauthenticated public endpoint to this local server. Bearer token authentication at the local bridge is defence in depth, not a substitute for tunnel authentication.
4. Store the token privately, not in Git, command history, screenshots or browser code. Use an isolated runtime secret source. Rotate if exposed.
5. Complete negative remote tests for missing/invalid token, forbidden tools, oversized requests, replay, unauthorised tenant, and disconnected tunnel. Verify Level 2 continues to operate.
6. Explicit local operator approval and local apply remain required. This same-UID prototype **does not provide independent approval isolation**. It must not be treated as production-authorised remote writing until this issue is addressed.
7. Do not enable production, live trading, or arbitrary command execution.

**Status:** code committed for review; remote transport, client registration, independent approval isolation, and Android acceptance are not yet complete.
