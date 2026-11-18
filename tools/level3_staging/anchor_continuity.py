"""Independent audit anchor continuity checks (offline; no storage provisioning).

An auditor must retrieve the previous trusted receipt from an external,
broker-inaccessible append-only store. This module rejects rollback and
same-height equivocation. It does not establish external durability itself.
"""
from tools.level3_staging.external_anchor import verify_anchor

class AnchorContinuityDenied(ValueError):
    pass

def verify_continuity(previous, current):
    """Require monotonic chain growth relative to a previously trusted receipt.

    The independent auditor must also verify the new receipt's signature and
    independently persist it before acknowledging a new checkpoint.
    """
    if not isinstance(previous, dict) or not isinstance(current, dict):
        raise AnchorContinuityDenied("invalid anchor receipt")
    required={"version","audience","count","last_sequence","head_hash"}
    if set(previous)!=required or set(current)!=required:
        raise AnchorContinuityDenied("invalid receipt fields")
    if previous["version"]!=1 or current["version"]!=1 or previous["audience"]!=current["audience"]:
        raise AnchorContinuityDenied("audience or version changed")
    for receipt in (previous,current):
        if (type(receipt["count"]) is not int or type(receipt["last_sequence"]) is not int
            or receipt["count"]<0 or receipt["last_sequence"]<receipt["count"]
            or not isinstance(receipt["head_hash"],str) or len(receipt["head_hash"])!=64
            or any(ch not in "0123456789abcdef" for ch in receipt["head_hash"])):
            raise AnchorContinuityDenied("invalid receipt values")
    if (current["count"]<previous["count"] or
        current["last_sequence"]<previous["last_sequence"]):
        raise AnchorContinuityDenied("audit rollback")
    if (current["count"]==previous["count"] or
        current["last_sequence"]==previous["last_sequence"]):
        if current!=previous:
            raise AnchorContinuityDenied("same-height audit equivocation")
        return "unchanged"
    # Monotonic heads alone do not prove ancestry. A trusted independent
    # auditor must validate the intervening chain before storing the new head.
    return "requires_chain_verification"
