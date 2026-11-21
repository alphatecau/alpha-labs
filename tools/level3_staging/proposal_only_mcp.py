"""Proposal-only MCP facade for Level 3 staging.

Never exposes apply/approve, shell, arbitrary file writes or Level 2 methods.
This is an offline dispatcher, NOT a deployed HTTP adapter or connected tunnel.
"""
import json

try:
    from .termux_local_approval import Refused, propose
except ImportError:
    from termux_local_approval import Refused, propose

TOOLS = [{
    "name": "level3_propose_create",
    "description": "Submit an allowlisted staging create proposal for separate operator review. Does not create target.",
    "inputSchema": {
        "type": "object",
        "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["path", "content"],
        "additionalProperties": False,
    },
}]


def dispatch(message, root):
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return None
    method = message.get("method")
    ident = message.get("id")
    if ident is None:
        return None
    if method == "initialize":
        result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {"listChanged": False}},
                  "serverInfo": {"name": "level3-proposal-only", "version": "0.1.0"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        try:
            params = message.get("params")
            if not isinstance(params, dict) or params.get("name") != "level3_propose_create":
                raise Refused("tool denied")
            args = params.get("arguments")
            if not isinstance(args, dict) or set(args) != {"path", "content"}:
                raise Refused("arguments denied")
            receipt = propose(root, args["path"], args["content"])
            result = {"content": [{"type": "text", "text": json.dumps(receipt, sort_keys=True)}]}
        except (Refused, OSError, ValueError, KeyError, TypeError):
            result = {"isError": True, "content": [{"type": "text", "text": "request denied"}]}
    else:
        return {"jsonrpc": "2.0", "id": ident,
                "error": {"code": -32601, "message": "method not found"}}
    return {"jsonrpc": "2.0", "id": ident, "result": result}
