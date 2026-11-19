"""Interactive Android/Termux auditor key setup; never prints secret material.

Usage: python -m tools.level3_staging.auditor_android_init
"""
import getpass
import os
from pathlib import Path

from tools.level3_staging.auditor_software_key import EncryptedAuditorSigner
from tools.level3_staging.auditor_file_store import AuditorFileStore


def main():
    home = Path.home() / ".local" / "state" / "alpha-labs-auditor"
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    if home.is_symlink() or home.stat().st_mode & 0o077:
        raise SystemExit("Refusing insecure auditor directory")
    key_file = home / "auditor-ed25519.enc.json"
    if key_file.exists():
        raise SystemExit("Auditor key already exists; refusing replacement")
    first = getpass.getpass("New auditor passphrase (not echoed): ")
    second = getpass.getpass("Repeat auditor passphrase: ")
    if first != second:
        raise SystemExit("Passphrases do not match; no key created")
    signer = EncryptedAuditorSigner.create(key_file, first)
    AuditorFileStore(home)
    print("Auditor software key initialised in private local storage.")
    print("Public key (hex; safe to share):", signer.public_key.hex())
    print("Private key not displayed. Store a secure offline backup.")
    print("STAGING ONLY: Drive mirror authentication and live Neon access are not configured.")


if __name__ == "__main__":
    main()
