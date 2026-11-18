"""Experimental stdio MCP transport for Level 3 proposals ONLY.

No apply/write tool is exposed. This module is intentionally safe to run
without granting filesystem write access. Requires Python 3.10+.
"""
import json
import os
import sys
from pathlib import Path
from tools.level3_staging.controlled_write import propose

PROTOCOL = "2025-06-18"
TOOLS = [
    {
        "name": "level3_propose_create",
        "description": "Validate a proposed staging file creation; never writes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    }
]

def dispatch(message, root):
    method = message.get("method")
    ident = message.get("id")
    if ident is None:
        return None
    try:
        if method == "initialize":
            result = {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "alpha-labs-level3-proposal-only", "version": "0.1.0"},
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            params = message.get("params") or {}
            if params.get("name") != "level3_propose_create":
                raise ValueError("unknown tool")
            args = params.get("arguments") or {}
            if set(args) != {"path", "content"}:
                raise ValueError("invalid arguments")
            proposal = propose(root, args["path"], args["content"])
            result = {"content": [{"type": "text", "text": json.dumps(proposal, sort_keys=True)}]}
        else:
            return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": "method not found"}}
        return {"jsonrpc": "2.0", "id": ident, "result": result}
    except (ValueError, OSError, TypeError, KeyError) as exc:
        return {"jsonrpc": "2.0", "id": ident, "result": {"isError": True, "content": [{"type": "text", "text": "proposal refused: " + type(exc).__name__}]}} if method == "tools/call" else {"jsonrpc": "2.0", "id": ident, "error": {"code": -32602, "message": "invalid request"}}

def main():
    root = os.environ.get("LEVEL3_STAGING_ROOT")
    if not root or not Path(root).is_dir():
        raise SystemExit("LEVEL3_STAGING_ROOT must point to an existing isolated staging checkout")
    for line in sys.stdin:
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                continue
            reply = dispatch(message, root)
            if reply is not None:
                print(json.dumps(reply, separators=(",", ":")), flush=True)
        except (json.JSONDecodeError, UnicodeError):
            continue

if __name__ == "__main__":
    main()
