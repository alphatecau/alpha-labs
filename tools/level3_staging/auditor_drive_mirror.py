"""Independent-account Google Drive checkpoint mirror for staging.

Adapter takes a separately authenticated Drive transport with:
create_once(name, data) -> opaque file_id and read(file_id) -> bytes.
No broker credentials are accepted. Drive is mutable; local trusted head
remains authoritative. A successful mirror is NOT WORM retention.
"""
import hashlib
import json
import re


class MirrorDenied(ValueError):
    pass


class DriveCheckpointMirror:
    def __init__(self, transport):
        self.transport = transport

    def retain_and_verify(self, key, raw):
        if not isinstance(raw, bytes) or not re.fullmatch(r"level3-checkpoints/alpha-labs-level3_[A-Za-z0-9_-]+/[0-9]{20}-[0-9a-f]{64}\.json", key):
            raise MirrorDenied("invalid checkpoint")
        file_id = self.transport.create_once(key, raw)
        if not isinstance(file_id, str) or not file_id:
            raise MirrorDenied("missing Drive file identifier")
        returned = self.transport.read(file_id)
        if returned != raw:
            raise MirrorDenied("Drive checkpoint readback mismatch")
        return {"file_id": file_id, "sha256": hashlib.sha256(returned).hexdigest()}


class MirroredAuditorStore:
    """Require independently verified mirror before advancing local CAS head."""

    def __init__(self, local_store, mirror):
        self.local_store = local_store
        self.mirror = mirror
        self._pending = {}

    def read_latest(self, audience):
        return self.local_store.read_latest(audience)

    def create_once(self, key, raw):
        self.local_store.create_once(key, raw)
        self._pending[key] = self.mirror.retain_and_verify(key, raw)

    def read(self, key):
        return self.local_store.read(key)

    def advance_latest(self, audience, expected, new):
        # Require evidence for this exact signed object, not another object
        # with coincidentally matching bytes or a stale prior operation.
        if not isinstance(new, dict) or not isinstance(new.get("receipt"), dict):
            raise MirrorDenied("invalid signed checkpoint")
        receipt = new["receipt"]
        if receipt.get("audience") != audience:
            raise MirrorDenied("checkpoint audience mismatch")
        raw = json.dumps(new, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        digest = hashlib.sha256(raw).hexdigest()
        key = (f"level3-checkpoints/{audience.replace(':', '_')}/"
               f"{receipt['last_sequence']:020d}-{digest}.json")
        if self._pending.get(key, {}).get("sha256") != digest:
            raise MirrorDenied("checkpoint has no verified external mirror")
        advanced = self.local_store.advance_latest(audience, expected, new)
        if advanced:
            self._pending.pop(key, None)
        return advanced
