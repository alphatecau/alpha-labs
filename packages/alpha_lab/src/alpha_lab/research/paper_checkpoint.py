"""Research-only authenticated journal checkpoint envelopes.

The signing key must be supplied independently and never stored beside the
SQLite journal or checkpoint. HMAC detects forgery without the key, but cannot
detect rollback of both files to an older legitimately signed state.
"""
import hmac
import json
from hashlib import sha256


def _payload(sequence, head):
    if type(sequence) is not int or sequence < 0:
        raise ValueError("invalid checkpoint sequence: HALT")
    if not isinstance(head, str) or len(head) != 64 or any(
            char not in "0123456789abcdef" for char in head):
        raise ValueError("invalid checkpoint hash: HALT")
    return {"version": 1, "sequence": sequence, "head": head}


def _key(secret):
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise ValueError("independent checkpoint key of at least 32 bytes required: HALT")
    return secret


def _envelope(payload, secret):
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(_key(secret), body, sha256).hexdigest()
    return json.dumps({**payload, "mac": signature}, sort_keys=True, separators=(",", ":"))


def seal_checkpoint(*, sequence, head, secret):
    return _envelope(_payload(sequence, head), secret)


def seal_state_checkpoint(*, owner, sequence, head, secret):
    """Version two commits the complete state and binds it to its owner."""
    payload = _payload(sequence, head)
    return _envelope({**payload, "version": 2, "owner": owner}, secret)


def read_state_checkpoint(envelope, *, owner, secret):
    try:
        data = json.loads(envelope)
        expected = seal_state_checkpoint(owner=owner, sequence=data["sequence"],
                                         head=data["head"], secret=secret)
        if not hmac.compare_digest(expected, envelope):
            raise ValueError("checkpoint authentication or version mismatch: HALT")
        return data["sequence"], data["head"]
    except (TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("missing or malformed state checkpoint: HALT") from exc


def verify_sealed_checkpoint(journal, envelope, *, secret):
    _key(secret)
    try:
        data = json.loads(envelope)
        if not isinstance(data, dict) or set(data) != {"version", "sequence", "head", "mac"}:
            raise ValueError("checkpoint envelope malformed: HALT")
        if type(data["version"]) is not int or data["version"] != 1:
            raise ValueError("unsupported checkpoint version: HALT")
        payload = _payload(data["sequence"], data["head"])
        if not isinstance(data["mac"], str) or len(data["mac"]) != 64:
            raise ValueError("checkpoint MAC malformed: HALT")
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        expected = hmac.new(secret, body, sha256).hexdigest()
        if not hmac.compare_digest(expected, data["mac"]):
            raise ValueError("checkpoint authentication failure: HALT")
    except (TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("checkpoint envelope malformed: HALT") from exc
    return journal.verify_checkpoint(
        trusted_sequence=payload["sequence"], trusted_head=payload["head"])
