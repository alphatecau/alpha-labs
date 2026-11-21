"""MCP dispatcher for restricted Termux staging create-only operations."""
import json
import sys
from tools.level3_staging.termux_local_approval import Refused, propose, apply

TOOLS = [
    {"name": "level3_propose_create", "description": "Queue an allowlisted staging file creation for local operator approval; does not write target file.",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                     "required": ["path", "content"], "additionalProperties": False}},
    {"name": "level3_apply_approved_create", "description": "Apply one locally approved create-only request; refuses missing approval.",
     "inputSchema": {"type": "object", "properties": {"request_id": {"type": "string"}},
                     "required": ["request_id"], "additionalProperties": False}},
]


def dispatch(message, root):
    if not isinstance(message, dict) or message.get("id") is None:
        return None
    ident, method = message["id"], message.get("method")
    if method == "initialize":
        result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {"listChanged": False}},
                  "serverInfo": {"name": "termux-level3-local-staging", "version": "0.1.0"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        try:
            params = message.get("params")
            if not isinstance(params, dict):
                raise Refused("invalid params")
            args = params.get("arguments")
            if not isinstance(args, dict):
                raise Refused("invalid arguments")
            if params.get("name") == "level3_propose_create" and set(args) == {"path", "content"}:
                receipt = propose(root, args["path"], args["content"])
            elif params.get("name") == "level3_apply_approved_create" and set(args) == {"request_id"}:
                receipt = apply(root, args["request_id"])
            else:
                raise Refused("tool or arguments refused")
            result = {"content": [{"type": "text", "text": json.dumps(receipt, sort_keys=True)}]}
        except (Refused, OSError, ValueError, KeyError, TypeError) as exc:
            result = {"isError": True, "content": [{"type": "text", "text": "request denied: " + type(exc).__name__}]}
    else:
        return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": "method not found"}}
    return {"jsonrpc": "2.0", "id": ident, "result": result}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    for line in sys.stdin:
        try:
            reply = dispatch(json.loads(line), args.root)
            if reply is not None:
                print(json.dumps(reply, separators=(",", ":")), flush=True)
        except (ValueError, UnicodeError):
            continue


if __name__ == "__main__":
    main()
