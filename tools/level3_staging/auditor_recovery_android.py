"""Read-only Android inspection of an explicitly named interrupted checkpoint.

Usage: python -m tools.level3_staging.auditor_recovery_android <checkpoint-key>
No credentials, signing key or writes; never auto-promotes evidence.
"""
import argparse
from pathlib import Path

from tools.level3_staging.auditor_file_store import AuditorFileStore
from tools.level3_staging.auditor_rclone_drive import RcloneAuditorDrive
from tools.level3_staging.auditor_recovery import inspect_recovery
from tools.level3_staging.auditor_checkpoint_verify import AUDIENCE, PUBLIC_KEY, FOLDER


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint_key", help="Exact existing level3-checkpoints/...json key")
    args = parser.parse_args(argv)
    root = Path.home() / ".local/state/alpha-labs-auditor/checkpoints"
    report = inspect_recovery(
        AuditorFileStore(root),
        RcloneAuditorDrive("auditor", FOLDER),
        args.checkpoint_key, AUDIENCE, PUBLIC_KEY,
    )
    print("Recovery inspection:", report["state"])
    print("Audit sequence:", report["receipt"]["last_sequence"])
    print("Audit head:", report["receipt"]["head_hash"])
    print("Trusted pointer changed: NO")
    print("No automatic recovery, no Neon writes, no Drive writes")


if __name__ == "__main__":
    main()
