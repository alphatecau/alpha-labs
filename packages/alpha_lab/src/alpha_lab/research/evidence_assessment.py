"""Fail-closed chronological research evidence assessment, never trade authorisation."""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
from datetime import datetime
from hashlib import sha256
import json
from math import isfinite
from alpha_lab.strategy_evidence import evaluate_oos

def _canonical_sha(document: dict) -> str:
    unsigned = {k: v for k, v in document.items() if k != "evidence_sha256"}
    return sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()

def assess_evidence(folds: list[dict], *, additional_cost_per_period: float) -> dict:
    """Review only: historical folds are not independent sealed OOS evidence."""
    report = {"status": "INSUFFICIENT_EVIDENCE", "trading_enabled": False,
              "holdout_independently_sealed": False, "reasons": [],
              "fold_count": len(folds), "observation_count": 0}
    if not folds:
        report["reasons"].append("NO_EVIDENCE")
        return report
    seen = set()
    fold_ids = set()
    prior_timestamp = None
    returns = []
    fold_returns = []
    closed_trades = 0
    try:
        if not isinstance(additional_cost_per_period, (int, float)) or isinstance(additional_cost_per_period, bool) or not isfinite(additional_cost_per_period) or additional_cost_per_period < 0:
            raise ValueError("INVALID_COST_STRESS")
        source = None
        prior_end = None
        for fold in folds:
            if fold.get("trading_enabled") is not False or fold.get("schema") != "alpha-labs.chronological-replay-evidence.v1":
                raise ValueError("UNSUPPORTED_EVIDENCE_SCHEMA")
            if _canonical_sha(fold) != fold.get("evidence_sha256"):
                raise ValueError("EVIDENCE_CHECKSUM_MISMATCH")
            identity = (fold.get("dataset_sha256"), fold.get("quote_currency"),
                        fold.get("interval_minutes"), fold.get("code_revision_declared"))
            if source is None:
                source = identity
            elif source != identity:
                raise ValueError("MIXED_DATA_OR_CODE_REVISION")
            fold_id = fold.get("fold_id")
            if not isinstance(fold_id, str) or not fold_id.strip() or fold_id in fold_ids:
                raise ValueError("DUPLICATE_OR_INVALID_FOLD_ID")
            fold_ids.add(fold_id)
            if fold.get("holdout_independently_sealed") is not False or fold.get("executable_fills_verified") is not False:
                raise ValueError("UNSUPPORTED_VERIFICATION_CLAIM")
            rows = fold["periods"]
            if not rows or not isinstance(rows, list):
                raise ValueError("EMPTY_FOLD")
            start, end = fold["start_index"], fold["end_exclusive_index"]
            if len(rows) != end - start or (prior_end is not None and start < prior_end):
                raise ValueError("OVERLAPPING_OR_INCONSISTENT_FOLDS")
            prior_end = end
            initial = Decimal(fold["capital"])
            nav = initial
            for row in rows:
                stamp = row["timestamp_utc"]
                dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                if dt.tzinfo is None or dt.utcoffset().total_seconds() != 0:
                    raise ValueError("NON_UTC_TIMESTAMP")
                if prior_timestamp is not None and dt <= prior_timestamp:
                    raise ValueError("NONCHRONOLOGICAL_TIMESTAMP")
                prior_timestamp = dt
                if stamp in seen or row["fold_id"] != fold["fold_id"]:
                    raise ValueError("DUPLICATE_TIMESTAMP_OR_FOLD")
                seen.add(stamp)
                r = float(row["net_period_return"])
                if not isfinite(r) or r <= -1:
                    raise ValueError("INVALID_PERIOD_RETURN")
                nav = Decimal(row["net_modelled_nav"])
                if not nav.is_finite() or nav <= 0 or not initial.is_finite() or initial <= 0 or abs(float(nav / initial - 1) - r) > 1e-9:
                    raise ValueError("INVALID_NAV")
                returns.append(r)
                initial = nav
            if abs(nav - Decimal(fold["final_liquidatable_value"])) > Decimal("1e-8"):
                raise ValueError("FINAL_NAV_MISMATCH")
            fold_returns.append(float(nav / Decimal(fold["capital"]) - 1))
            closed_trades += fold["closed_trades"]
        if closed_trades < 0 or any(not isinstance(fold.get("closed_trades"), int) or isinstance(fold.get("closed_trades"), bool) or fold["closed_trades"] < 0 for fold in folds):
            raise ValueError("INVALID_TRADE_COUNT")
        report["observation_count"] = len(returns)
        screen = evaluate_oos(tuple(returns), trades=closed_trades,
                              fold_net_returns=tuple(fold_returns),
                              additional_cost_per_period=additional_cost_per_period)
        report["screen_status"] = screen.status
        report["screen_reasons"] = list(screen.reasons)
        report["lower_confidence_bound"] = screen.lower_confidence_bound
        report["max_drawdown"] = screen.max_drawdown
        report["reasons"].append("HOLDOUT_NOT_INDEPENDENTLY_SEALED")
        report["reasons"].append("MODELLED_FILLS_NOT_EXECUTABLE_QUOTES")
    except (KeyError, TypeError, ValueError, OverflowError, InvalidOperation, AttributeError) as exc:
        report["reasons"].append("INVALID_EVIDENCE:" + str(exc))
    return report
