"""Opt-in public Coinbase quote -> isolated simulated fill -> backup -> replay.

Never sends orders or uses Coinbase credentials. No automatic scheduling.
"""
import argparse
import sqlite3
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from alpha_lab.research.coinbase_paper_book import executable, fetch_book
from alpha_lab.research.live_paper_quotes import simulated_fill_estimate
from alpha_lab.research.paper_runtime import PaperRuntime


def rehearse(*, fetch=fetch_book, clock=lambda: datetime.now(timezone.utc)):
    # The temporary directory and both databases are never shared with working journals.
    with tempfile.TemporaryDirectory(prefix="alpha-stage9-paper-only-") as directory:
        journal = Path(directory) / "isolated.sqlite3"
        backup = Path(directory) / "backup.sqlite3"
        runtime = PaperRuntime(str(journal))
        try:
            assert runtime.recovery_verified and runtime.ledger.halted
            quote = fetch("BTC-USD")
            now = clock()
            if not executable(quote, now):
                raise ValueError("HALT: Coinbase quote failed validation")
            estimate = simulated_fill_estimate(
                quote, side="BUY", quantity="0.001", fee_rate="0.001", slippage_bps="5"
            )
            if estimate["simulated_only"] is not True or estimate["live_execution_authorised"] is not False:
                raise ValueError("HALT: simulation boundary violated")
            # Independently revalidate immediately before operator-only paper arming.
            now = clock()
            if not executable(quote, now):
                raise ValueError("HALT: Coinbase quote expired")
            runtime.enable(operator_approved=True)
            fill = runtime.execute(
                symbol="BTC-USD", side="BUY", quantity="0.001",
                reference_mid=estimate["reference_mid"],
                executed_price=estimate["executed_price"], fee=estimate["fee"],
                quote_timestamp=quote.exchange_at, now=now, marks={},
                proposed_loss="2", aggregate_open_risk="0",
                gross_notional="0", peak_nav="10000", day_start_nav="10000",
                operator_approved=True, order_id="stage9-single-paper-only",
                details={"source": quote.source, "sequence": quote.source_sequence,
                         "exchange_timestamp": quote.source_timestamp,
                         "live_execution_authorised": False},
            )
            if fill["simulated"] is not True:
                raise ValueError("HALT: non-simulated fill")
            head = runtime.journal_head
            with sqlite3.connect(str(backup)) as destination:
                runtime.journal.connection.backup(destination)
                if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("HALT: backup integrity failure")
        finally:
            runtime.close()

        for path in (journal, backup):
            restored = PaperRuntime(str(path))
            try:
                if (not restored.recovery_verified or not restored.ledger.halted
                        or len(restored.events) != 1 or restored.journal_head != head
                        or restored.events[0]["order_id"] != "stage9-single-paper-only"):
                    raise ValueError("HALT: independent replay mismatch")
            finally:
                restored.close()
        return {"status": "PASS", "mode": "SIMULATION_ONLY",
                "fills": 1, "backup": "VERIFIED", "restart": "HALT",
                "live_execution_authorised": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approve-paper-only", action="store_true",
                        help="explicit consent for one isolated simulated fill")
    args = parser.parse_args()
    if not args.approve_paper_only:
        parser.error("HALT: --approve-paper-only required")
    print(rehearse())


if __name__ == "__main__":
    main()
