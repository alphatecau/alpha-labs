"""Stdio MCP worker using independent Unix-socket broker custody."""
import base64
import json
import os
import stat
import sys
from pathlib import Path
from tools.level3_staging.mcp_broker_worker import dispatch
from tools.level3_staging.startup_guard import verify_startup

def main():
    path=os.environ.get("LEVEL3_BROKER_SOCKET")
    if not path or not Path(path).is_socket():
        raise SystemExit("Level 3 broker socket missing")
    sock=Path(path)
    st=sock.stat()
    if not stat.S_ISSOCK(st.st_mode) or st.st_uid==os.getuid():
        raise SystemExit("Level 3 denied: broker must have independent UID")
    root=os.environ.get("LEVEL3_STAGING_ROOT")
    ledger=os.environ.get("LEVEL3_LEDGER_PATH")
    readiness_pub=os.environ.get("LEVEL3_READINESS_PUBLIC_KEY_B64")
    if not root or not ledger or not readiness_pub:
        raise SystemExit("Level 3 denied: independent readiness configuration missing")
    try:
        public_key=base64.b64decode(readiness_pub,validate=True)
    except (ValueError,TypeError) as exc:
        raise SystemExit("Level 3 denied: invalid readiness public key") from exc
    if len(public_key)!=32:
        raise SystemExit("Level 3 denied: invalid readiness public key length")
    verify_startup(os.environ.get("LEVEL3_READINESS_ATTESTATION"),public_key,root,ledger)
    for line in sys.stdin:
        try:
            message=json.loads(line)
            response=dispatch(message,path)
            if response is not None:
                print(json.dumps(response,separators=(",",":")),flush=True)
        except (ValueError,TypeError):
            continue

if __name__=="__main__":
    main()
