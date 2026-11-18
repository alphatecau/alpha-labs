"""Offline Level 3 signed-create MCP dispatcher; never run without isolated operator approval."""
import json
import sqlite3
from tools.level3_staging.signed_create import Denied, apply, validate

PROTOCOL = "2025-06-18"
TOOL = {"name":"level3_apply_signed_create",
        "description":"Create an allowlisted staging file only with a separately issued Ed25519 approval.",
        "inputSchema":{"type":"object","properties":{
            "path":{"type":"string"},"content":{"type":"string"},
            "approval":{"type":"object"},"signature":{"type":"string"}},
            "required":["path","content","approval","signature"],"additionalProperties":False}}

def dispatch(message, root, ledger, public_key):
    if not isinstance(message, dict):
        return None
    method, ident = message.get("method"), message.get("id")
    if ident is None:
        return None
    if method == "initialize":
        result = {"protocolVersion":PROTOCOL,"capabilities":{"tools":{"listChanged":False}},
                  "serverInfo":{"name":"alpha-labs-level3-signed-staging","version":"0.1.0"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools":[TOOL]}
    elif method == "tools/call":
        try:
            params = message.get("params")
            if not isinstance(params, dict) or params.get("name") != TOOL["name"]:
                raise Denied("tool refused")
            args = params.get("arguments")
            if not isinstance(args, dict) or set(args) != {"path","content","approval","signature"}:
                raise Denied("arguments refused")
            validate(args["path"], args["content"])
            receipt = apply(root, ledger, public_key, args["approval"], args["signature"],
                            args["path"], args["content"])
            result = {"content":[{"type":"text","text":json.dumps(receipt,sort_keys=True)}]}
        except (Denied, OSError, ValueError, TypeError, KeyError, RuntimeError, sqlite3.Error) as exc:
            result = {"isError":True,"content":[{"type":"text","text":"write refused: "+type(exc).__name__}]}
    else:
        return {"jsonrpc":"2.0","id":ident,"error":{"code":-32601,"message":"method not found"}}
    return {"jsonrpc":"2.0","id":ident,"result":result}
