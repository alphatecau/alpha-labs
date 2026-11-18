"""Stdio entrypoint for the isolated signed-write MCP prototype.

Never reuse the Level 2 tunnel, identity, credentials or checkout.
"""
import base64
import json
import os
import sys
from pathlib import Path
from tools.level3_staging.mcp_signed import dispatch
from tools.level3_staging.startup_guard import verify_startup

def main():
    root = os.environ.get("LEVEL3_STAGING_ROOT")
    ledger = os.environ.get("LEVEL3_LEDGER_PATH")
    public_b64 = os.environ.get("LEVEL3_APPROVER_PUBLIC_KEY_B64")
    if not root or not ledger or not public_b64:
        raise SystemExit("missing Level 3 isolated staging configuration")
    if not Path(root).is_dir():
        raise SystemExit("isolated staging checkout does not exist")
    try:
        public_key = base64.b64decode(public_b64, validate=True)
    except (ValueError, TypeError) as exc:
        raise SystemExit("invalid public key") from exc
    if len(public_key) != 32:
        raise SystemExit("invalid Ed25519 public key length")
    verify_startup(os.environ.get('LEVEL3_READINESS_ATTESTATION'), public_key, root, ledger)
    for line in sys.stdin:
        try:
            message = json.loads(line)
            reply = dispatch(message, root, ledger, public_key)
            if reply is not None:
                print(json.dumps(reply, separators=(",", ":")), flush=True)
        except (ValueError, UnicodeError, TypeError):
            continue

if __name__ == "__main__":
    main()
