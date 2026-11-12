"""Single-writer, offline paper-order bridge. No HTTP endpoint or broker execution.

This adapter is NOT multi-process safe; staging must supply exclusive writer
ownership before admitting requests. Quotes are supplied by a trusted caller.
"""
from datetime import datetime, timezone
import json
import re
from alpha_lab.research.live_paper_quotes import quote_is_fresh, simulated_fill_estimate
from alpha_lab.research.paper_simulator import number

_ORDER_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")

class LivePaperBridge:
    def __init__(self, runtime):
        self.runtime = runtime

    def submit(self, *, order_id, quote, side, quantity, now, marks,
               proposed_loss, aggregate_open_risk, gross_notional,
               peak_nav, day_start_nav, operator_approved=False,
               fee_rate="0.001", slippage_bps="5"):
        if not isinstance(order_id, str) or not _ORDER_ID.fullmatch(order_id):
            raise ValueError("invalid order id")
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("UTC now required")
        if not self.runtime.recovery_verified or self.runtime.ledger.halted:
            raise PermissionError("HALT: paper runtime disabled")
        if operator_approved is not True:
            raise PermissionError("HALT: operator approval required")
        # The durable journal is the idempotency source of truth after restart.
        for (raw,) in self.runtime.journal.connection.execute(
                "SELECT payload FROM events ORDER BY seq"):
            event = json.loads(raw)
            if event.get("order_id") == order_id:
                if event.get("symbol") != quote.symbol or event.get("side") != side or event.get("quantity") != str(number(quantity)):
                    raise ValueError("order id reused with different order")
                return {"status": "ALREADY_COMMITTED", "order_id": order_id,
                        "fill": event, "mode": "SIMULATION_ONLY"}
        if not quote_is_fresh(quote, now=now):
            self.runtime.ledger.halt()
            raise PermissionError("HALT: stale or unverified quote")
        estimate = simulated_fill_estimate(quote, side=side, quantity=quantity,
                                           fee_rate=fee_rate, slippage_bps=slippage_bps)
        # Existing PaperRuntime independently enforces risk and persists a hash-chained fill.
        fill = self.runtime.execute(
            symbol=quote.symbol, side=side, quantity=quantity,
            reference_mid=estimate["reference_mid"],
            executed_price=estimate["executed_price"], fee=estimate["fee"],
            quote_timestamp=quote.observed_at, now=now, marks=marks,
            proposed_loss=proposed_loss, aggregate_open_risk=aggregate_open_risk,
            gross_notional=gross_notional, peak_nav=peak_nav,
            day_start_nav=day_start_nav, operator_approved=operator_approved,
            order_id=order_id)
        return {"status": "SIMULATED_FILL", "order_id": order_id,
                "fill": fill, "mode": "SIMULATION_ONLY"}
