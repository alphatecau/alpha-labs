"""Stdio entrypoint for the isolated signed-write MCP prototype.

Never reuse the Level 2 tunnel, identity, credentials or checkout.
"""
import base64
import json
import os
import sys
import stat
from pathlib import Path
from tools.level3_staging.mcp_signed import dispatch
from tools.level3_staging.startup_guard import verify_startup

def main():
    # This legacy direct-ledger worker cannot enforce independent custody.
    # No production deployment path exists until a broker-backed worker is implemented.
    if os.environ.get('LEVEL3_OFFLINE_TEST_ONLY') != '1':
        raise SystemExit('Level 3 startup denied: broker-backed custody not implemented')
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
    audit = os.environ.get("LEVEL3_AUDIT_PATH")
    if not audit or Path(audit).parent.resolve().is_relative_to(Path(root).resolve()):
        raise SystemExit("Level 3 startup denied: protected external audit required")
    ledger_parent = Path(ledger).parent.resolve(strict=True)
    audit_parent = Path(audit).parent.resolve(strict=True)
    for directory in (ledger_parent, audit_parent):
        mode = directory.stat().st_mode
        if not stat.S_ISDIR(mode) or mode & 0o077:
            raise SystemExit("Level 3 startup denied: private storage directory required")
    if Path(ledger).is_symlink() or Path(audit).is_symlink():
        raise SystemExit("Level 3 startup denied: storage symlink")
    from tools.level3_staging.audit_chain import verify
    try:
        verify(audit)
    except (OSError, ValueError) as exc:
        raise SystemExit("Level 3 startup denied: audit integrity failure") from exc
    if Path(ledger).exists():
        from tools.level3_staging.audit_reconcile import inspect_outbox
        try:
            audit_status = inspect_outbox(ledger, audit)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise SystemExit("Level 3 startup denied: audit reconciliation error") from exc
        if audit_status["blocked"]:
            raise SystemExit("Level 3 startup denied: unreconciled audit evidence")
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
