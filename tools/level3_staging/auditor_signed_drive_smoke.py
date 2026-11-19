"""Explicit staging-only signed synthetic evidence test using Android's auditor key.

This is NOT a PostgreSQL audit-chain checkpoint or production evidence.
Private key and passphrase never leave the device.
"""
import getpass
import hashlib
import json
import secrets
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from tools.level3_staging.auditor_rclone_drive import RcloneAuditorDrive
from tools.level3_staging.auditor_software_key import EncryptedAuditorSigner


FOLDER = "118pwq_VOAGeeS1NOTXmoA4ZVEx4AcMo6"


def main():
    key_path = Path.home() / ".local/state/alpha-labs-auditor/auditor-ed25519.enc.json"
    signer = EncryptedAuditorSigner.open(
        key_path, getpass.getpass("Auditor passphrase (not echoed): ")
    )
    payload = {
        "kind": "alpha-labs-level3-synthetic-signature-smoke-v1",
        "nonce": secrets.token_hex(16),
        "production_evidence": False,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    signature = signer.sign(canonical)
    Ed25519PublicKey.from_public_bytes(signer.public_key).verify(signature, canonical)
    signed = {
        "payload": payload,
        "public_key_hex": signer.public_key.hex(),
        "signature_hex": signature.hex(),
    }
    raw = json.dumps(signed, sort_keys=True, separators=(",", ":")).encode()
    name = ("level3-checkpoints/alpha-labs-level3_smoke/"
            + "0" * 20 + "-" + hashlib.sha256(raw).hexdigest() + ".json")
    drive = RcloneAuditorDrive("auditor", FOLDER)
    remote = drive.create_once(name, raw)
    recovered = drive.read(remote)
    if recovered != raw:
        raise RuntimeError("FAIL: Drive readback mismatch")
    loaded = json.loads(recovered)
    check = json.dumps(loaded["payload"], sort_keys=True, separators=(",", ":")).encode()
    Ed25519PublicKey.from_public_bytes(bytes.fromhex(loaded["public_key_hex"])).verify(
        bytes.fromhex(loaded["signature_hex"]), check
    )
    if loaded["public_key_hex"] != signer.public_key.hex():
        raise RuntimeError("FAIL: unexpected auditor identity")
    print("PASS: persistent Android auditor key signed synthetic evidence")
    print("PASS: Google Drive upload, readback, and Ed25519 verification")
    print("Public key:", signer.public_key.hex())
    print("Evidence SHA256:", hashlib.sha256(recovered).hexdigest())
    print("NOT a PostgreSQL checkpoint or production acceptance")


if __name__ == "__main__":
    main()
