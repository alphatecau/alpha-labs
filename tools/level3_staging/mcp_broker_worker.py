"""Broker-backed Level 3 MCP: worker has no ledger, audit or signing key."""
import json
from tools.level3_staging.broker import request
from tools.level3_staging.mcp_signed import PROTOCOL,TOOL
from tools.level3_staging.signed_create import Denied,validate

def dispatch(message,socket_path):
    if not isinstance(message,dict) or message.get("id") is None:
        return None
    ident=message["id"]
    method=message.get("method")
    if method=="initialize":
        result={"protocolVersion":PROTOCOL,"capabilities":{"tools":{"listChanged":False}},
                "serverInfo":{"name":"alpha-labs-level3-broker-worker","version":"0.2.0"}}
    elif method=="ping":
        result={}
    elif method=="tools/list":
        result={"tools":[TOOL]}
    elif method=="tools/call":
        try:
            params=message.get("params")
            if not isinstance(params,dict) or params.get("name")!=TOOL["name"]:
                raise Denied("tool refused")
            args=params.get("arguments")
            if not isinstance(args,dict) or set(args)!={"path","content","approval","signature"}:
                raise Denied("arguments refused")
            validate(args["path"],args["content"])
            receipt=request(socket_path,args)
            result={"content":[{"type":"text","text":json.dumps(receipt,sort_keys=True)}]}
        except (Denied,OSError,ValueError,TypeError,KeyError,TimeoutError):
            result={"isError":True,"content":[{"type":"text","text":"broker write refused"}]}
    else:
        return {"jsonrpc":"2.0","id":ident,"error":{"code":-32601,"message":"method not found"}}
    return {"jsonrpc":"2.0","id":ident,"result":result}
