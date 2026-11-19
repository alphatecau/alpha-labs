"""Read-only Android verification of the last signed staging checkpoint.

No signing key, Neon credentials, or database writes required.
Detects altered/missing local checkpoint and Drive mirror; cannot prove WORM.
"""
import hashlib
import json
from pathlib import Path

from tools.level3_staging.auditor_file_store import AuditorFileStore
from tools.level3_staging.auditor_rclone_drive import RcloneAuditorDrive
from tools.level3_staging.external_anchor import verify_anchor

AUDIENCE = "alpha-labs-level3:staging"
PUBLIC_KEY = bytes.fromhex(
    "e48e95f7e6024b162b562b0a1e952150b2d810774948229bdc39fe03aa5986c4"
)
FOLDER = "118pwq_VOAGeeS1NOTXmoA4ZVEx4AcMo6"


def verify(store, drive):
    signed = store.read_latest(AUDIENCE)
    if not isinstance(signed, dict) or not isinstance(signed.get("receipt"), dict):
        raise ValueError("BLOCKED: missing or invalid trusted local latest checkpoint")
    receipt = signed["receipt"]
    verify_anchor(signed, PUBLIC_KEY, AUDIENCE, receipt)
    raw = json.dumps(signed, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    digest = hashlib.sha256(raw).hexdigest()
    key = (
        f"level3-checkpoints/{AUDIENCE.replace(':', '_')}/"
        f"{receipt['last_sequence']:020d}-{digest}.json"
    )
    if store.read(key) != raw:
        raise ValueError("BLOCKED: local signed checkpoint missing or altered")
    if drive.read(key) != raw:
        raise ValueError("BLOCKED: remote Drive checkpoint missing or altered")
    return {"sha256": digest, "count": receipt["count"], "last_sequence": receipt["last_sequence"], "head_hash": receipt["head_hash"]}


def main():
    root = Path.home() / ".local/state/alpha-labs-auditor/checkpoints"
    result = verify(
        AuditorFileStore(root),
        RcloneAuditorDrive("auditor", FOLDER),
    )
    print("PASS: signed trusted latest and local checkpoint verified")
    print("PASS: independent Google Drive mirror byte-for-byte verified")
    print("Checkpoint SHA256:", result["sha256"])
    print("Audit event count:", result["count"])
    print("Audit head hash:", result["head_hash"])
    print("Read-only check; Google Drive is NOT immutable/WORM")


if __name__ == "__main__":
    main()
