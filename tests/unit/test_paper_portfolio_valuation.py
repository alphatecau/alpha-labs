import unittest
from decimal import Decimal
from alpha_lab.research.paper_simulator import PaperLedger
from alpha_lab.research.paper_portfolio_valuation import derive_portfolio

class PortfolioValuationTests(unittest.TestCase):
    def test_derived_nav_and_gross_exposure(self):
        ledger=PaperLedger("1000")
        ledger.enable_simulation(operator_approved=True)
        ledger.fill(symbol="BTC",side="BUY",quantity="2",reference_mid="100",executed_price="100",fee="2")
        ledger.fill(symbol="ETH",side="BUY",quantity="1",reference_mid="50",executed_price="50",fee="1")
        state=derive_portfolio(ledger,{"BTC":"110","ETH":"40"})
        self.assertEqual(state.cash,Decimal("747"))
        self.assertEqual(state.nav,Decimal("1007"))
        self.assertEqual(state.gross_notional,Decimal("260"))
    def test_missing_mark_and_bad_mark_halt(self):
        ledger=PaperLedger("1000")
        ledger.enable_simulation(operator_approved=True)
        ledger.fill(symbol="BTC",side="BUY",quantity="1",reference_mid="100",executed_price="100",fee="0")
        for marks in ({},{"BTC":"0"},{"BTC":"NaN"},{"BTC":"-1"}):
            with self.assertRaisesRegex(ValueError,"HALT"):
                derive_portfolio(ledger,marks)
    def test_cash_only_portfolio(self):
        state=derive_portfolio(PaperLedger("1000"),{})
        self.assertEqual(state.nav,Decimal("1000"))
        self.assertEqual(state.gross_notional,Decimal("0"))
if __name__=="__main__":
    unittest.main()
