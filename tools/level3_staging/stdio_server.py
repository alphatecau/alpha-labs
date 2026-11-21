"""Local, proposal-only MCP 3 stdio transport. No remote listener or apply tool.

Launch with: python -m tools.level3_staging.stdio_server /path/to/approved/workspace
The client process inherits the same UID: this is NOT a security boundary.
"""
import json
import sys
from pathlib import Path

try:
    from .proposal_only_mcp import dispatch
except ImportError:
    from proposal_only_mcp import dispatch

MAX_LINE = 65536


def serve(root, source=None, sink=None):
    source = source if source is not None else sys.stdin.buffer
    sink = sink if sink is not None else sys.stdout
    for raw in source:
        if len(raw) > MAX_LINE:
            # Refuse oversized messages without attempting to parse or echo secrets.
            continue
        try:
            message = json.loads(raw)
            if not isinstance(message, dict):
                continue
            if message.get("jsonrpc") != "2.0":
                continue
            if "id" not in message:
                # Notifications, including notifications/initialized, never get responses.
                continue
            response = dispatch(message, root)
            if response is not None:
                sink.write(json.dumps(response, separators=(",", ":"), ensure_ascii=True) + "\n")
                sink.flush()
        except (ValueError, UnicodeError, TypeError):
            # Malformed client input cannot cause a file operation or crash the server.
            continue


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        raise SystemExit("usage: python -m tools.level3_staging.stdio_server WORKSPACE")
    root = Path(args[0]).resolve(strict=True)
    if not root.is_dir():
        raise SystemExit("workspace must be a directory")
    serve(root)


if __name__ == "__main__":
    main()
