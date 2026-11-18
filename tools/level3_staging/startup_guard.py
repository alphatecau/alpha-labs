"""Fail-closed signed startup attestation for the Level 3 worker.

A signed attestation records independently verified deployment evidence; it does
not itself establish UID separation, file protection, or audit immutability.
"""
import base64
import json
import os
import stat
import time
from pathlib import Path
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from tools.level3_staging.readiness import Gate
from tools.level3_staging.signed_create import canonical

def verify_startup(attestation_file, public_key, root, ledger, now=None):
    if not attestation_file:
        raise SystemExit("Level 3 startup denied: missing signed readiness attestation")
    p=Path(attestation_file)
    try:
        if p.is_symlink() or not stat.S_ISREG(p.stat().st_mode) or p.stat().st_size > 8192:
            raise ValueError("invalid attestation file")
        record=json.loads(p.read_text(encoding="utf-8"))
        if set(record)!={"evidence","signature"}:
            raise ValueError("invalid attestation envelope")
        evidence=record["evidence"]
        required={"schema","root","ledger","expires_at",*vars(Gate()).keys()}
        if not isinstance(evidence,dict) or set(evidence)!=required:
            raise ValueError("invalid evidence fields")
        if evidence["schema"] != 1 or type(evidence["expires_at"]) is not int:
            raise ValueError("invalid evidence schema")
        clock=int(time.time() if now is None else now)
        if not clock < evidence["expires_at"] <= clock+3600:
            raise ValueError("expired or overlong attestation")
        if evidence["root"] != str(Path(root).resolve(strict=True)):
            raise ValueError("staging root mismatch")
        if evidence["ledger"] != str(Path(ledger).resolve(strict=False)):
            raise ValueError("ledger mismatch")
        gates={k:evidence[k] for k in vars(Gate())}
        if any(type(v) is not bool for v in gates.values()) or not Gate(**gates).may_activate():
            raise ValueError("unverified readiness gates")
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            base64.b64decode(record["signature"],validate=True),canonical(evidence))
        return True
    except (OSError, ValueError, TypeError, KeyError, InvalidSignature) as exc:
        raise SystemExit("Level 3 startup denied: invalid readiness evidence") from exc
