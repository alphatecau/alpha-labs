"""Operator-only offline approval signer. NEVER run in the MCP worker process.

Private key supplied as a protected file, not a command-line argument or environment value.
Review exact path/content/hash before issuing any signature.
"""
import argparse
import base64
import hashlib
import json
import os
import stat
import sys
import time
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from tools.level3_staging.signed_create import canonical, validate

def sign(key_file, path, content, ttl=120, now=None, nonce=None):
    payload, digest = validate(path, content)
    if not isinstance(ttl, int) or not 1 <= ttl <= 300:
        raise ValueError("TTL must be 1..300 seconds")
    key_file = Path(key_file)
    if key_file.is_symlink():
        raise PermissionError("signing key symlink refused")
    st = key_file.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_mode & 0o077:
        raise PermissionError("signing key must be private regular file")
    raw = key_file.read_bytes()
    if len(raw) != 32:
        raise ValueError("signing key must contain 32 raw bytes")
    key = Ed25519PrivateKey.from_private_bytes(raw)
    clock = int(time.time() if now is None else now)
    approval = {"operation":"create","path":path,"sha256":digest,
                "nonce":nonce or os.urandom(32).hex(),"expires_at":clock+ttl}
    signature = base64.b64encode(key.sign(canonical(approval))).decode()
    return {"approval":approval,"signature":signature}

def main():
    parser = argparse.ArgumentParser(description="Offline operator approval only")
    parser.add_argument("--private-key-file",required=True)
    parser.add_argument("--path",required=True)
    parser.add_argument("--content-file",required=True)
    parser.add_argument("--ttl",type=int,default=120)
    args = parser.parse_args()
    content = Path(args.content_file).read_text(encoding="utf-8")
    _, digest = validate(args.path, content)
    print(f"PATH: {args.path}\nSHA256: {digest}\nBYTES: {len(content.encode('utf-8'))}",file=sys.stderr)
    print("CONTENT BEGIN\n"+content+"\nCONTENT END",file=sys.stderr)
    if input("Type APPROVE to sign this exact content: ") != "APPROVE":
        raise SystemExit("operator declined")
    print(json.dumps(sign(args.private_key_file,args.path,content,args.ttl),sort_keys=True))

if __name__ == "__main__":
    main()
