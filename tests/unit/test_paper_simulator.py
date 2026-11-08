"""Adversarial checks for the offline-only paper simulator."""
from decimal import Decimal
import pytest
from alpha_lab.research.paper_simulator import PaperLedger

def buy(ledger, **changes):
    values = dict(symbol="BTC", side="BUY", quantity="2",
                  reference_mid="100", executed_price="101", fee="1")
    values.update(changes)
    return ledger.fill(**values)

def test_halt_default_and_explicit_approval():
    p = PaperLedger()
    with pytest.raises(PermissionError, match="HALT"):
        buy(p)
    with pytest.raises(PermissionError, match="approval"):
        p.enable_simulation()
    p.enable_simulation(operator_approved=True)
    assert buy(p)["simulated"] is True

def test_independent_cash_position_nav_and_cost():
    p = PaperLedger("1000")
    p.enable_simulation(operator_approved=True)
    a = buy(p)
    b = p.fill(symbol="BTC", side="SELL", quantity="0.5",
               reference_mid="110", executed_price="109", fee="0.5")
    assert p.cash == Decimal("851.5")
    assert p.positions["BTC"] == Decimal("1.5")
    assert p.nav({"BTC": "110"}) == Decimal("1016.5")
    assert Decimal(a["shortfall_vs_mid"]) == Decimal("2")
    assert Decimal(b["shortfall_vs_mid"]) == Decimal("0.5")
    assert p.fills[1]["previous_hash"] == p.fills[0]["audit_hash"]

@pytest.mark.parametrize("mutation", [
    {"quantity": "NaN"}, {"quantity": "-1"}, {"fee": "-1"},
    {"side": "SHORT"}, {"executed_price": "Infinity"},
    {"quantity": "1000"}, {"simulated_only": False},
    {"observed_quote": False},
])
def test_adversarial_rejections_without_fill(mutation):
    p = PaperLedger("1000")
    p.enable_simulation(operator_approved=True)
    with pytest.raises((ValueError, PermissionError)):
        buy(p, **mutation)
    assert p.fills == [] and p.cash == Decimal("1000")

def test_naked_short_and_missing_marks():
    p = PaperLedger("1000")
    p.enable_simulation(operator_approved=True)
    with pytest.raises(ValueError, match="naked short"):
        p.fill(symbol="BTC", side="SELL", quantity="1",
               reference_mid="100", executed_price="100", fee="0")
    buy(p)
    with pytest.raises(ValueError, match="HALT"):
        p.nav({})
    assert p.halted

def test_manual_halt_blocks_additional_orders():
    p = PaperLedger()
    p.enable_simulation(operator_approved=True)
    p.halt()
    with pytest.raises(PermissionError):
        buy(p)
