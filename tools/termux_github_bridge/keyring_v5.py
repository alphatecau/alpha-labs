"""Explicit, fingerprint-pinned Ed25519 public-key enrolment.

No network access. Private signing keys are never accepted.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
import ed25519_protocol_v5 as protocol
import signed_protocol_v4 as v4

KEY_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

def decode_key(encoded):
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise v4.Rejected("invalid key encoding") from exc
    if len(raw) != 32 or base64.b64encode(raw).decode("ascii") != encoded:
        raise v4.Rejected("invalid public key")
    Ed25519PublicKey.from_public_bytes(raw)
    return raw

def fingerprint(raw):
    return hashlib.sha256(b"termux-v5-public-key\x00" + raw).hexdigest()

def read_keyring(path):
    path = Path(path)
    if not path.exists():
        return {}
    if path.is_symlink():
        raise v4.Rejected("keyring symlink denied")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise v4.Rejected("insecure keyring permissions")
    ring = json.loads(path.read_text())
    if type(ring) is not dict or len(ring) > 32:
        raise v4.Rejected("invalid keyring")
    for key_id, encoded in ring.items():
        if not KEY_ID.fullmatch(key_id) or type(encoded) is not str:
            raise v4.Rejected("invalid keyring entry")
        decode_key(encoded)
    return ring

def write_keyring(path, ring):
    path = Path(path)
    if path.is_symlink():
        raise v4.Rejected("keyring symlink denied")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.stat().st_mode & 0o077:
        raise v4.Rejected("insecure keyring directory")
    fd, name = tempfile.mkstemp(prefix=".keyring-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(ring, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def enrol(path, key_id, encoded, expected_fingerprint):
    if type(key_id) is not str or not KEY_ID.fullmatch(key_id):
        raise v4.Rejected("invalid key id")
    raw = decode_key(encoded)
    if type(expected_fingerprint) is not str or not re.fullmatch(r"[0-9a-f]{64}", expected_fingerprint):
        raise v4.Rejected("fingerprint must be 64 lowercase hex characters")
    import hmac
    if not hmac.compare_digest(fingerprint(raw), expected_fingerprint):
        raise v4.Rejected("fingerprint mismatch")
    ring = read_keyring(path)
    if key_id in ring:
        raise v4.Rejected("key id already enrolled; revoke before replacement")
    ring[key_id] = encoded
    write_keyring(path, ring)

def revoke(path, key_id):
    ring = read_keyring(path)
    if key_id not in ring:
        raise v4.Rejected("unknown key id")
    del ring[key_id]
    write_keyring(path, ring)

def trusted_keys(path):
    return {name: Ed25519PublicKey.from_public_bytes(decode_key(encoded))
            for name, encoded in read_keyring(path).items()}

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyring", required=True)
    sub = parser.add_subparsers(dest="action", required=True)
    add = sub.add_parser("enrol")
    add.add_argument("--key-id", required=True)
    add.add_argument("--public-key-base64", required=True)
    add.add_argument("--expected-fingerprint", required=True)
    rm = sub.add_parser("revoke")
    rm.add_argument("--key-id", required=True)
    args = parser.parse_args(argv)
    if args.action == "enrol":
        enrol(args.keyring, args.key_id, args.public_key_base64, args.expected_fingerprint)
        print("Public key enrolled")
    else:
        revoke(args.keyring, args.key_id)
        print("Public key revoked")

if __name__ == "__main__":
    main()
