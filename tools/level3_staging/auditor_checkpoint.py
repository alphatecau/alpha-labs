"""Auditor-side checkpoint verification and persistence protocol.

The auditor's signing key MUST be held by a separate signing service/KMS and
never supplied to this module. External storage must enforce create-only,
no-delete permissions and retain an independent trusted latest-head pointer.
"""
import hashlib
import json
from tools.level3_staging.anchor_continuity import verify_continuity
from tools.level3_staging.external_anchor import canonical_receipt, verify_anchor
from tools.level3_staging.postgres_custody import verify_audit_chain


class CheckpointDenied(ValueError):
    pass


def build_checkpoint(conn, audience, previous=None):
    """Read and verify every PostgreSQL audit event; reject unanchored rollbacks.

    Caller must obtain previous from independently controlled auditor storage.
    """
    if not isinstance(audience, str) or not audience.startswith("alpha-labs-level3:"):
        raise CheckpointDenied("invalid audience")
    head = verify_audit_chain(conn)
    if head["count"] == 0:
        raise CheckpointDenied("empty chain cannot establish nonempty audit evidence")
    receipt = {"version": 1, "audience": audience, **head}
    if previous is not None:
        verdict = verify_continuity(previous, receipt)
        if verdict == "requires_chain_verification":
            # verify_audit_chain validates this database's internal chain; the
            # auditor must additionally compare the old head at old sequence.
            row = conn.execute(
                "SELECT event_hash FROM level3_custody.audit_event WHERE sequence=%s",
                (previous["last_sequence"],),
            ).fetchone()
            if row is None or row[0].strip() != previous["head_hash"]:
                raise CheckpointDenied("previous anchored head is not ancestor")
    return receipt


def sign_and_retain(receipt, signer, store, public_key, previous=None):
    """Sign with an auditor-controlled interface and retain before acknowledgement.

    signer.sign(data) must be backed by independently controlled persistent KMS.
    store.create_once(key, bytes) must reject overwrites; store.read(key) must
    return the exact durable bytes. No automatic retries after ambiguous writes.
    """
    if not isinstance(receipt, dict):
        raise CheckpointDenied("invalid receipt")
    if previous is not None:
        if verify_continuity(previous, receipt) == "unchanged":
            raise CheckpointDenied("duplicate checkpoint")
    payload = canonical_receipt(receipt)
    signature = signer.sign(payload)
    import base64
    if not isinstance(signature, bytes) or len(signature) != 64:
        raise CheckpointDenied("invalid signature bytes")
    signed = {"receipt": receipt, "signature": base64.b64encode(signature).decode("ascii")}
    verify_anchor(signed, public_key, receipt["audience"],
                  {k: receipt[k] for k in ("count", "last_sequence", "head_hash")})
    raw = json.dumps(signed, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    key = f"level3-checkpoints/{receipt['audience'].replace(':','_')}/{receipt['last_sequence']:020d}-{hashlib.sha256(raw).hexdigest()}.json"
    store.create_once(key, raw)
    recovered = store.read(key)
    if recovered != raw:
        raise CheckpointDenied("external readback mismatch")
    loaded = json.loads(recovered)
    verify_anchor(loaded, public_key, receipt["audience"],
                  {k: receipt[k] for k in ("count", "last_sequence", "head_hash")})
    return {"key": key, "sha256": hashlib.sha256(recovered).hexdigest(), "signed": loaded}
