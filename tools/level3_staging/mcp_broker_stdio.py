"""Stdio MCP worker using independent Unix-socket broker custody."""
import json
import os
import stat
import sys
from pathlib import Path
from tools.level3_staging.mcp_broker_worker import dispatch

def main():
    path=os.environ.get("LEVEL3_BROKER_SOCKET")
    if not path or not Path(path).is_socket():
        raise SystemExit("Level 3 broker socket missing")
    sock=Path(path)
    st=sock.stat()
    if not stat.S_ISSOCK(st.st_mode) or st.st_uid==os.getuid():
        raise SystemExit("Level 3 denied: broker must have independent UID")
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
