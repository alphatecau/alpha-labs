"""Operator-controlled Ed25519 signer. No network or GitHub access.

Run only on an independently secured signing host, never on the Termux worker.
Never print or upload private key material.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import secrets
import stat
import sys
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import ed25519_protocol_v5 as protocol
import signed_protocol_v4 as v4

def create_key(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("symlink forbidden")
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

def load_private_key(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("symlink forbidden")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise ValueError("private key must be a regular 0600 file")
    raw = path.read_bytes()
    if len(raw) != 32:
        raise ValueError("invalid private key size")
    return Ed25519PrivateKey.from_private_bytes(raw)

def sign_task(key, key_id, device, operation, repo, now=None):
    if not isinstance(key_id, str) or not 1 <= len(key_id) <= 64 or any(c not in protocol.KEY_ID_FIELDS for c in key_id):
        raise ValueError("invalid key id")
    if not isinstance(device, str) or not v4.DEVICE.fullmatch(device):
        raise ValueError("invalid device")
    if operation not in v4.OPS or repo not in v4.REPOS:
        raise ValueError("operation or repository denied")
    issued = int(time.time()) if now is None else int(now)
    task = {"schema": 4, "device": device, "nonce": secrets.token_hex(16),
            "issued_at": issued, "expires_at": issued + 120,
            "operation": operation, "repo": repo}
    signed = protocol.DOMAIN + key_id.encode("ascii") + b"\x00" + v4.canonical(task)
    return {"task": task, "key_id": key_id,
            "signature": base64.b64encode(key.sign(signed)).decode("ascii")}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    init = sub.add_parser("init")
    init.add_argument("--private-key", required=True)
    sign = sub.add_parser("sign")
    sign.add_argument("--private-key", required=True)
    sign.add_argument("--key-id", required=True)
    sign.add_argument("--device", required=True)
    sign.add_argument("--operation", choices=sorted(v4.OPS), required=True)
    sign.add_argument("--repo", choices=sorted(v4.REPOS), required=True)
    args = parser.parse_args(argv)
    if args.action == "init":
        pub = create_key(args.private_key)
        print("Public verification key (base64; safe to transfer out of band):")
        print(base64.b64encode(pub).decode("ascii"))
    else:
        key = load_private_key(args.private_key)
        print(json.dumps(sign_task(key, args.key_id, args.device, args.operation, args.repo),
                         sort_keys=True, separators=(",", ":")))

if __name__ == "__main__":
    main()
