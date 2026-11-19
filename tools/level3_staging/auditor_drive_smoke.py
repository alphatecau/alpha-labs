"""Explicit, non-sensitive Android staging Drive write/readback smoke test.

Creates one random-named test object under the pinned auditor folder.
Does not touch signing keys, credentials, audit heads, or live trading.
"""
import hashlib
import secrets

from tools.level3_staging.auditor_rclone_drive import RcloneAuditorDrive


AUDITOR_FOLDER = "118pwq_VOAGeeS1NOTXmoA4ZVEx4AcMo6"


def main():
    drive = RcloneAuditorDrive("auditor", AUDITOR_FOLDER)
    # Clearly synthetic data; no private or production evidence.
    raw = b"alpha-labs-level3-synthetic-drive-smoke-v1:" + secrets.token_hex(16).encode()
    key = ("level3-checkpoints/alpha-labs-level3_smoke/"
           + "0" * 20 + "-" + hashlib.sha256(raw).hexdigest() + ".json")
    file_id = drive.create_once(key, raw)
    if drive.read(file_id) != raw:
        raise RuntimeError("FAIL: Drive readback differs")
    try:
        drive.create_once(key, raw)
    except Exception as exc:
        if type(exc).__name__ != "RcloneDriveDenied":
            raise
    else:
        raise RuntimeError("FAIL: duplicate upload accepted")
    print("PASS: synthetic Drive upload, readback, and duplicate denial")
    print("Staging test object:", key)
    print("No auditor key, audit head, or trade was used")


if __name__ == "__main__":
    main()
