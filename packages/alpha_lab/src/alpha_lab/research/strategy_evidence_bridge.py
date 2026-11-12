"""Explicit compatibility gate for existing Alpha Labs research reports.

Legacy aggregate-only reports cannot be fed into a bootstrap screen as if they
contained chronological per-period OOS observations. This is deliberate.
"""
from alpha_lab.strategy_evidence import evaluate_oos, ValidationConfig
from alpha_lab.research.promotion_authority import decide_strategy_promotion

def screen_research_report(report: dict, *, config: ValidationConfig = ValidationConfig()) -> dict:
    if not isinstance(report, dict) or report.get("trading_enabled") is not False:
        raise ValueError("Research-only report required")
    # Never infer missing return observations from summary metrics.
    required = ("oos_period_net_returns", "oos_fold_net_returns",
                "oos_trade_count", "additional_cost_per_period")
    missing = tuple(key for key in required if key not in report)
    if missing:
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "trading_enabled": False,
            "promotion_authorised": False,
            "live_trading_authorised": False,
            "missing_fields": missing,
            "reason": "Existing aggregate summaries do not prove chronological OOS observations",
        }
    # Additional provenance requirements are mandatory before screening.
    if (report.get("point_in_time_provenance_verified") is not True or
        report.get("costs_modelled") is not True or
        report.get("holdout_independently_sealed") is not True):
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "trading_enabled": False,
            "promotion_authorised": False,
            "live_trading_authorised": False,
            "missing_fields": tuple(k for k in (
                "point_in_time_provenance_verified", "costs_modelled",
                "holdout_independently_sealed") if report.get(k) is not True),
            "reason": "Required independent evidence has not been established",
        }
    result = evaluate_oos(
        tuple(report["oos_period_net_returns"]),
        trades=report["oos_trade_count"],
        fold_net_returns=tuple(report["oos_fold_net_returns"]),
        additional_cost_per_period=report["additional_cost_per_period"],
        config=config,
    )
    authority = decide_strategy_promotion(assessment=report)
    return {"status": result.status, "trading_enabled": False,
            "promotion_authorised": authority["promotion_authorised"],
            "live_trading_authorised": authority["live_trading_authorised"],
            "reasons": result.reasons, "observations": result.observations,
            "lower_confidence_bound": result.lower_confidence_bound,
            "max_drawdown": result.max_drawdown}
