"""Independent, deterministic Decimal oracle for research-only long/cash accounting.

This oracle is deliberately structured as a separate event-to-state reducer, not
a call to the production reconstruction implementation. Synthetic evidence only.
"""
import random
import unittest
from decimal import Decimal

from alpha_lab.research.phase1_accounting import reconstruct


def dec(value):
    return Decimal(str(value))


def reference_ledger(events, marks, initial, liquidation_bps):
    balance = dec(initial)
    inventory = {symbol: dec(0) for symbol in marks}
    fees = dec(0)
    gross = dec(0)
    for event in events:
        symbol = event["symbol"]
        units = dec(event["quantity"])
        price = dec(event["price"])
        charge = dec(event["fee"])
        trade_value = units * price
        signed_units = units if event["side"] == "BUY" else -units
        inventory[symbol] += signed_units
        balance -= trade_value + charge if signed_units > 0 else -(trade_value - charge)
        fees += charge
        gross += trade_value
    haircut = dec(1) - dec(liquidation_bps) / dec(10000)
    liquidation_value = sum((inventory[s] * dec(marks[s]) * haircut for s in marks), dec(0))
    return balance, inventory, fees, gross, balance + liquidation_value


class IndependentAccountingOracleTests(unittest.TestCase):
    def test_randomised_cash_inventory_fees_and_nav(self):
        rng = random.Random(20261109)
        markets = ("BTC", "ETH", "SOL")
        for scenario in range(1000):
            balance = dec(10000)
            inventory = {s: dec(0) for s in markets}
            events = []
            for _ in range(rng.randrange(1, 30)):
                symbol = rng.choice(markets)
                price = dec(rng.randrange(10, 5000)) / 10
                buy = not inventory[symbol] or rng.choice((True, False))
                units = dec(rng.randrange(1, 11)) / 10
                if not buy:
                    units = min(units, inventory[symbol])
                fee = units * price * dec("0.001")
                value = units * price
                delta = -(value + fee) if buy else value - fee
                if buy and balance + delta < 0:
                    continue
                events.append({"symbol": symbol, "side": "BUY" if buy else "SELL",
                               "quantity": str(units), "price": str(price),
                               "fee": str(fee), "cash_delta": str(delta)})
                inventory[symbol] += units if buy else -units
                balance += delta
            marks = {s: str(dec(rng.randrange(10, 5000)) / 10) for s in markets}
            haircut = rng.choice((0, 10, 25, 100, 250))
            oracle = reference_ledger(events, marks, "10000", haircut)
            actual = reconstruct(events, marks, starting_cash="10000", liquidation_bps=str(haircut))
            with self.subTest(scenario=scenario):
                self.assertEqual(dec(actual["cash"]), oracle[0])
                self.assertEqual({s: dec(q) for s, q in actual["positions"].items()}, oracle[1])
                self.assertEqual(dec(actual["fees"]), oracle[2])
                self.assertEqual(dec(actual["gross_executed_notional"]), oracle[3])
                self.assertEqual(dec(actual["final_liquidation_nav"]), oracle[4])
                self.assertEqual(actual["order_count"], len(events))

    def test_adversarial_events_fail_closed(self):
        valid = {"symbol": "BTC", "side": "BUY", "quantity": "1",
                 "price": "100", "fee": "1", "cash_delta": "-101"}
        mutations = (
            {"cash_delta": "-100"},
            {"quantity": "NaN"},
            {"price": "Infinity"},
            {"fee": "-1"},
            {"side": "SHORT"},
            {"symbol": "UNKNOWN"},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises((ValueError, KeyError)):
                reconstruct([{**valid, **mutation}], {"BTC": "120"}, starting_cash="1000")

    def test_cost_haircut_is_monotonic(self):
        orders = [{"symbol": "BTC", "side": "BUY", "quantity": "2",
                   "price": "100", "fee": "1", "cash_delta": "-201"}]
        navs = [
            dec(reconstruct(orders, {"BTC": "120"}, starting_cash="1000",
                            liquidation_bps=str(bps))["final_liquidation_nav"])
            for bps in (0, 25, 100, 500)
        ]
        self.assertEqual(navs, sorted(navs, reverse=True))
        self.assertEqual(navs[0] - navs[2], dec("2.4"))


if __name__ == "__main__":
    unittest.main()
