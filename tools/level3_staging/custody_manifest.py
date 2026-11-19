"""Offline content-addressed custody manifest, excluding secrets and payloads."""
import hashlib
import re


class ManifestDenied(ValueError):
    """Malformed or inconsistent manifest."""


def make_manifest(parent_id, file_id, payload):
    if not all(isinstance(value, str) and value for value in (parent_id, file_id)):
        raise ManifestDenied("invalid file identity")
    if not isinstance(payload, bytes):
        raise ManifestDenied("payload must be bytes")
    digest = hashlib.sha256(payload).hexdigest()
    return {"version": 1, "parent_id": parent_id, "file_id": file_id,
            "sha256": digest, "size": len(payload), "name": digest + ".bin"}


def verify_manifest(manifest, readback):
    if not isinstance(manifest, dict) or set(manifest) != {
        "version", "parent_id", "file_id", "sha256", "size", "name"
    }:
        raise ManifestDenied("invalid manifest fields")
    digest = manifest["sha256"]
    if (type(manifest["version"]) is not int or manifest["version"] != 1
            or not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or type(manifest["size"]) is not int or manifest["size"] < 0
            or not all(isinstance(manifest[k], str) and manifest[k]
                       for k in ("parent_id", "file_id"))
            or manifest["name"] != digest + ".bin"):
        raise ManifestDenied("invalid manifest values")
    if not isinstance(readback, bytes) or len(readback) != manifest["size"]:
        raise ManifestDenied("invalid readback size")
    if hashlib.sha256(readback).hexdigest() != digest:
        raise ManifestDenied("readback hash mismatch")
    return True
