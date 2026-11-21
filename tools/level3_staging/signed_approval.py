"""Offline Ed25519 approval verification for a future isolated Level 3 writer.

Verification only. This module cannot issue approvals, write files or expose MCP.
Public keys are pinned by the independently controlled writer operator.
"""
import base64
import hashlib
import json
import re
import time

PATH = re.compile(r"^(docs/level3-staging/[A-Za-z0-9_-]+\.md|tests/level3-staging/[A-Za-z0-9_-]+\.txt)$")
HEX = re.compile(r"^[0-9a-f]{64}$")
NONCE = re.compile(r"^[0-9a-f]{32}$")
FIELDS = frozenset({"version", "operation", "environment", "path", "sha256", "nonce", "expires_at"})


class ApprovalDenied(ValueError):
    pass


def canonical(payload):
    if not isinstance(payload, dict) or set(payload) != FIELDS:
        raise ApprovalDenied("invalid approval fields")
    if payload["version"] != 1 or payload["operation"] != "create" or payload["environment"] != "level3-staging":
        raise ApprovalDenied("unsupported approval scope")
    if not isinstance(payload["path"], str) or not PATH.fullmatch(payload["path"]):
        raise ApprovalDenied("path refused")
    if not isinstance(payload["sha256"], str) or not HEX.fullmatch(payload["sha256"]):
        raise ApprovalDenied("invalid digest")
    if not isinstance(payload["nonce"], str) or not NONCE.fullmatch(payload["nonce"]):
        raise ApprovalDenied("invalid nonce")
    if type(payload["expires_at"]) is not int or payload["expires_at"] < 1:
        raise ApprovalDenied("invalid expiry")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def verify(payload, signature_b64, public_key_b64, path, content, *, now=None):
    message = canonical(payload)
    if not isinstance(path, str) or path != payload["path"]:
        raise ApprovalDenied("path mismatch")
    if not isinstance(content, bytes) or len(content) > 32768:
        raise ApprovalDenied("content refused")
    if hashlib.sha256(content).hexdigest() != payload["sha256"]:
        raise ApprovalDenied("content digest mismatch")
    current = int(time.time()) if now is None else now
    if type(current) is not int or payload["expires_at"] <= current or payload["expires_at"] > current + 300:
        raise ApprovalDenied("approval expired or excessive lifetime")
    try:
        signature = base64.b64decode(signature_b64, validate=True)
        public = base64.b64decode(public_key_b64, validate=True)
        if len(signature) != 64 or len(public) != 32:
            raise ApprovalDenied("invalid key or signature length")
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        Ed25519PublicKey.from_public_bytes(public).verify(signature, message)
    except Exception as exc:  # fail closed if crypto dependency is unavailable
        raise ApprovalDenied("signature verification failed") from exc
    return {"nonce": payload["nonce"], "path": path, "sha256": payload["sha256"]}
