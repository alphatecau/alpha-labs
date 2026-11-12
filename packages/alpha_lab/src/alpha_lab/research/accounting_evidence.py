"""Offline research evidence envelopes and independently sourced statement checks.

SHA-256 establishes byte integrity, NOT source authenticity. Authenticated
external evidence requires a separate trusted signature/attestation workflow.
"""
import hashlib
import json
from decimal import Decimal
from alpha_lab.research.phase1_accounting import D
from alpha_lab.research.pnl_reporting import report_pnl


def canonical_digest(payload):
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def evidence_envelope(payload, *, source_kind="SYNTHETIC", source_reference=None):
    if source_kind not in ("SYNTHETIC", "UNVERIFIED_EXTERNAL", "AUTHENTICATED_EXTERNAL"):
        raise ValueError("Unsupported evidence source")
    if source_kind == "AUTHENTICATED_EXTERNAL":
        raise ValueError("Authenticated provenance requires external signature verification")
    return {"source_kind": source_kind, "source_reference": source_reference,
            "sha256": canonical_digest(payload), "authenticated": False,
            "promotion_eligible": False}


def reconcile_statement(orders, closing_prices, statement, *,
                        starting_cash="10000", liquidation_bps="0",
                        require_fill_ids=True):
    """Compare an independently supplied statement with the reconstructed ledger.

    A matching statement alone does not establish its source authenticity.
    Reject missing or unsupported accounting fields rather than infer them.
    """
    if not isinstance(statement, dict):
        raise ValueError("Statement must be a mapping")
    required = ("final_cash", "final_liquidation_nav", "total_fees")
    if any(k not in statement for k in required):
        raise ValueError("Statement missing required accounting field")
    pnl = report_pnl(orders, closing_prices, starting_cash=starting_cash,
                     liquidation_bps=liquidation_bps,
                     require_fill_ids=require_fill_ids)
    cash = D(starting_cash)
    for fill in orders:
        cash += D(fill["cash_delta"])
    observed = {"final_cash": cash,
                "final_liquidation_nav": D(pnl["final_liquidation_nav"]),
                "total_fees": D(pnl["fees"])}
    for field in required:
        if D(statement[field]) != observed[field]:
            raise ValueError("Independent statement mismatch: " + field)
    return {"reconciled": True, "authenticated": False,
            "promotion_eligible": False,
            "status": "MATCHED_UNAUTHENTICATED",
            "ledger_sha256": canonical_digest(orders),
            "statement_sha256": canonical_digest(statement)}
