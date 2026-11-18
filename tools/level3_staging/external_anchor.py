"""Independent signed custody-head receipts.

An auditor holds the Ed25519 private key outside the broker/Neon trust domain.
A signature alone is NOT an independent anchor: the receipt must also be
persisted in an external append-only store inaccessible to the broker.
"""
import base64
import binascii
import json
import re
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

def canonical_receipt(receipt):
    return json.dumps(receipt,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()

def verify_anchor(signed,public_key,expected_audience,current_head):
    if not isinstance(signed,dict) or set(signed)!={"receipt","signature"}:
        raise ValueError("invalid signed receipt")
    receipt=signed["receipt"]
    if not isinstance(receipt,dict) or set(receipt)!={"version","audience","count","last_sequence","head_hash"}:
        raise ValueError("invalid receipt fields")
    if (receipt["version"]!=1 or receipt["audience"]!=expected_audience or
        type(receipt["count"]) is not int or receipt["count"]<0 or
        type(receipt["last_sequence"]) is not int or receipt["last_sequence"]<receipt["count"] or
        not isinstance(receipt["head_hash"],str) or
        re.fullmatch("[0-9a-f]{64}",receipt["head_hash"]) is None):
        raise ValueError("invalid receipt values")
    if receipt["count"]!=current_head["count"] or receipt["head_hash"]!=current_head["head_hash"] or receipt["last_sequence"]!=current_head["last_sequence"]:
        raise ValueError("custody head diverges from external anchor")
    try:
        sig=base64.b64decode(signed["signature"],validate=True)
        Ed25519PublicKey.from_public_bytes(public_key).verify(sig,canonical_receipt(receipt))
    except (InvalidSignature, ValueError, TypeError, binascii.Error) as exc:
        raise ValueError("invalid auditor signature") from exc
    return True
