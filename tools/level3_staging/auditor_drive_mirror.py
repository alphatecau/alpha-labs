"""Independent-account Google Drive checkpoint mirror for staging.

Adapter takes a separately authenticated Drive transport with:
create_once(name, data) -> opaque file_id and read(file_id) -> bytes.
No broker credentials are accepted. Drive is mutable; local trusted head
remains authoritative. A successful mirror is NOT WORM retention.
"""
import hashlib


class MirrorDenied(ValueError):
    pass


class DriveCheckpointMirror:
    def __init__(self, transport):
        self.transport = transport

    def retain_and_verify(self, key, raw):
        if not isinstance(raw, bytes) or not key.startswith("level3-checkpoints/"):
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
        # Acknowledgement requires a mirrored, readback-verified checkpoint
        # from this process, not merely a pre-existing local object.
        import hashlib
        import json
        raw = json.dumps(new, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        digest = hashlib.sha256(raw).hexdigest()
        if not any(item["sha256"] == digest for item in self._pending.values()):
            raise MirrorDenied("checkpoint has no verified external mirror")
        return self.local_store.advance_latest(audience, expected, new)
