import pytest
from alpha_lab.research.screenshot_evidence import reconcile_rows, source_digest

HASH = "a" * 64

def row(t, amount, balance, kind="TRADE_RESULT"):
    return dict(date_time="2026-09-14T10:37:" + t, amount=amount,
                balance=balance, source_sha256=HASH, description=kind)

def test_statement_balance_and_commission():
    result = reconcile_rows([row("15", "1.00", "3.65"),
                             row("15", "-0.30", "3.35", "COMMISSION"),
                             row("39", "1.00", "4.35"),
                             row("39", "-0.30", "4.05", "COMMISSION")])
    assert result["observed_commissions"] == "0.60"
    assert result["ending_balance"] == "4.05"
    assert not result["broker_authenticated"]

@pytest.mark.parametrize("rows", [
    [row("15", "1.00", "3.65"), row("39", "1.00", "4.05")],
    [row("15", "1.00", "3.65"), row("15", "1.00", "3.65")],
    [row("39", "1.00", "4.35"), row("15", "-0.30", "4.05", "COMMISSION")],
    [row("15", "NaN", "3.65")],
    [row("15", "0.001", "3.65")],
    [row("15", "0.30", "3.65", "COMMISSION")],
    [dict(row("15", "1.00", "3.65"), account_id="sensitive")],
])
def test_fail_closed(rows):
    with pytest.raises(ValueError):
        reconcile_rows(rows)

def test_hash_original_bytes(tmp_path):
    file = tmp_path / "statement.png"
    file.write_bytes(b"test screenshot bytes")
    assert len(source_digest(file)) == 64
    assert source_digest(file) == source_digest(file)
