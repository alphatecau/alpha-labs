import unittest
from alpha_lab.research.screenshot_evidence import reconcile_rows, source_digest

HASH = "a" * 64

def row(t, amount, balance, kind="TRADE_RESULT"):
    return dict(date_time="2026-09-14T10:37:" + t, amount=amount,
                balance=balance, source_sha256=HASH, description=kind)

class ScreenshotEvidenceTests(unittest.TestCase):
    def test_statement_balance_and_commission(self):
        result = reconcile_rows([row("15", "1.00", "3.65"),
                                 row("15", "-0.30", "3.35", "COMMISSION"),
                                 row("39", "1.00", "4.35"),
                                 row("39", "-0.30", "4.05", "COMMISSION")])
        self.assertEqual(result["observed_commissions"], "0.60")
        self.assertEqual(result["ending_balance"], "4.05")
        self.assertFalse(result["broker_authenticated"])

    def test_fail_closed(self):
        cases = [
            [row("15", "1.00", "3.65"), row("39", "1.00", "4.05")],
            [row("15", "1.00", "3.65"), row("15", "1.00", "3.65")],
            [row("39", "1.00", "4.35"), row("15", "-0.30", "4.05", "COMMISSION")],
            [row("15", "NaN", "3.65")],
            [row("15", "0.001", "3.65")],
            [row("15", "0.30", "3.65", "COMMISSION")],
            [dict(row("15", "1.00", "3.65"), account_id="sensitive")],
        ]
        for rows in cases:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                reconcile_rows(rows)

    def test_hash_original_bytes(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "statement.png"
            file.write_bytes(b"test screenshot bytes")
            self.assertEqual(len(source_digest(file)), 64)
            self.assertEqual(source_digest(file), source_digest(file))

if __name__ == "__main__":
    unittest.main()
