"""Read-only Android runtime acceptance probe. Never starts the MCP worker."""
import importlib
import os
import sys
from pathlib import Path

def main():
    required=("tools.level3_staging.signed_create",
              "tools.level3_staging.mcp_signed",
              "tools.level3_staging.mcp_signed_stdio",
              "tools.level3_staging.startup_guard",
              "tools.level3_staging.audit_reconcile")
    for module in required:
        importlib.import_module(module)
    if not hasattr(os,"O_NOFOLLOW") or not hasattr(os,"O_EXCL"):
        raise SystemExit("FAIL: secure open flags unavailable")
    if sys.platform != "linux":
        raise SystemExit("FAIL: Level 3 runtime requires Linux")
    legacy=Path("tools/level3_staging/controlled_write.py")
    if not legacy.exists():
        raise SystemExit("FAIL: legacy test fixture unexpectedly missing")
    print("PASS: signed MCP imports and Linux filesystem flags")
    print("HOLD: legacy controlled_write.py excluded from runtime deployment")
    print("HOLD: independent UID, audit anchor, signed readiness and connector acceptance not proven")

if __name__=="__main__":
    main()
