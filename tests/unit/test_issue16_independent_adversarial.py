"""Independent adversarial arithmetic and fail-closed checks for Issue #16.

Synthetic fixtures only. These do not establish real fill costs, independent
archive provenance, production readiness or strategy profitability.
"""
from decimal import Decimal

import pytest

from alpha_lab.research.phase1_accounting import reconstruct, reconcile_simulation
from alpha_lab.research.phase1_evidence import (
    execution_cost_bridge, experiment_record, verify_registry,
    verify_signal_availability,
)
from alpha_lab.research.selection_gate import selection_aware_gate
from datetime import datetime, timezone, timedelta


def _orders():
    return [
        {"symbol": "BTC", "side": "BUY", "quantity": "2", "price": "100", "fee": "1", "cash_delta": "-201"},
        {"symbol": "BTC", "side": "SELL", "quantity": "0.5", "price": "120", "fee": "0.5", "cash_delta": "59.5"},
    ]


def test_independent_decimal_partial_sale_cash_and_liquidation_nav():
    result = reconstruct(_orders(), {"BTC": "110"}, starting_cash="1000", liquidation_bps="0.01")
    assert Decimal(result["cash"]) == Decimal("858.5")
    assert Decimal(result["positions"]["BTC"]) == Decimal("1.5")
    assert Decimal(result["fees"]) == Decimal("1.5")
    assert Decimal(result["final_liquidation_nav"]) == Decimal("1021.85")


@pytest.mark.parametrize("mutation", [
    {"cash_delta": "-200"}, {"fee": "-1"}, {"quantity": "NaN"},
    {"quantity": "Infinity"}, {"side": "SHORT"},
])
def test_forged_or_invalid_execution_rejected(mutation):
    orders = _orders()
    orders[0] = {**orders[0], **mutation}
    with pytest.raises((ValueError, KeyError)):
        reconstruct(orders, {"BTC": "110"}, starting_cash="1000")


def test_naked_short_and_negative_cash_rejected():
    sell = {"symbol": "BTC", "side": "SELL", "quantity": "1", "price": "100", "fee": "0", "cash_delta": "100"}
    with pytest.raises(ValueError, match="Naked"):
        reconstruct([sell], {"BTC": "100"})
    buy = {"symbol": "BTC", "side": "BUY", "quantity": "101", "price": "100", "fee": "0", "cash_delta": "-10100"}
    with pytest.raises(ValueError, match="Negative cash"):
        reconstruct([buy], {"BTC": "100"})


def test_forged_simulator_nav_rejected():
    simulation = {"orders": _orders(), "final_cash": "858.5", "final_nav": "9999", "total_fees": "1.5"}
    with pytest.raises(ValueError, match="Final NAV mismatch"):
        reconcile_simulation(simulation, {"BTC": "110"}, liquidation_bps="0.01")


def test_cost_bridge_independent_buy_and_sell_oracle():
    fills = [
        {"side": "BUY", "quantity": "2", "reference_mid": "100", "executed_price": "101", "fee": "0.5"},
        {"side": "SELL", "quantity": "1", "reference_mid": "110", "executed_price": "109", "fee": "0.25"},
    ]
    result = execution_cost_bridge(fills)
    assert Decimal(result["explicit_fees"]) == Decimal("0.75")
    assert Decimal(result["execution_shortfall_vs_mid"]) == Decimal("3")
    assert Decimal(result["combined_cost"]) == Decimal("3.75")
    assert result["spread_vs_impact_separately_identifiable"] is False


def test_tampered_experiment_registry_rejected_and_promotion_denied():
    record = experiment_record("hypothesis", "a" * 64, "commit", "data")
    assert record["record"]["promotion_authorised"] is False
    assert record["record"]["trading_enabled"] is False
    record["record"]["status"] = "PASS_ENGINEERING"
    with pytest.raises(ValueError, match="Tampered"):
        verify_registry([record])


def test_same_time_and_future_signal_rejected():
    execution = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
    for signal in (execution, execution + timedelta(seconds=1)):
        with pytest.raises(ValueError, match="Lookahead"):
            verify_signal_availability(signal, execution)


def test_perfect_five_fold_results_still_not_promotable():
    reports = [
        {"market": f"m{i}", "cost_bps_fee_and_slippage_each_side": 20,
         "folds": [{"return_pct": 1} for _ in range(5)]}
        for i in range(9)
    ]
    result = selection_aware_gate(reports)
    assert result["promotion_authorised"] is False
    assert result["statistical_validation"] == "NOT_ESTABLISHED"
    assert all(not item["statistically_significant"] for item in result["comparisons"])
