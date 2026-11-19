"""Android-only staging checkpoint of a NONEMPTY Neon audit chain.

Requires LEVEL3_AUDITOR_READONLY_DSN from a least-privilege read-only role.
Does not run until explicitly invoked. No credentials or passphrase logged.
"""
import getpass
import os
from pathlib import Path

from tools.level3_staging.auditor_checkpoint import verify_sign_and_retain
from tools.level3_staging.auditor_drive_mirror import DriveCheckpointMirror, MirroredAuditorStore
from tools.level3_staging.auditor_file_store import AuditorFileStore
from tools.level3_staging.auditor_rclone_drive import RcloneAuditorDrive
from tools.level3_staging.auditor_software_key import EncryptedAuditorSigner


def main():
    dsn = os.environ.get("LEVEL3_AUDITOR_READONLY_DSN")
    if not dsn:
        raise SystemExit("BLOCKED: set LEVEL3_AUDITOR_READONLY_DSN securely (not in chat)")
    import psycopg
    root = Path.home() / ".local/state/alpha-labs-auditor/checkpoints"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    signer = EncryptedAuditorSigner.open(
        Path.home() / ".local/state/alpha-labs-auditor/auditor-ed25519.enc.json",
        getpass.getpass("Auditor passphrase (not echoed): "),
    )
    store = MirroredAuditorStore(
        AuditorFileStore(root),
        DriveCheckpointMirror(RcloneAuditorDrive(
            "auditor", "118pwq_VOAGeeS1NOTXmoA4ZVEx4AcMo6"
        )),
    )
    with psycopg.connect(dsn, autocommit=True, connect_timeout=10) as conn:
        conn.execute("SET default_transaction_read_only = on")
        result = verify_sign_and_retain(
            conn, "alpha-labs-level3:staging", signer, store, signer.public_key
        )
    print("PASS: read-only Neon audit chain verified and signed")
    print("PASS: independently mirrored Drive checkpoint verified")
    print("Checkpoint SHA256:", result["sha256"])
    print("Public key:", signer.public_key.hex())
    print("Staging only; not WORM or production authorisation")


if __name__ == "__main__":
    main()
