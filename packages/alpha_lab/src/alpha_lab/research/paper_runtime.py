"""Offline paper runtime: replay journal before admitting new simulated fills.

No HTTP server, broker, external orders, background scheduler or credential access.
"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
from alpha_lab.research.paper_simulator import PaperLedger, number
from alpha_lab.research.paper_journal import PaperJournal
from alpha_lab.research.paper_checkpoint import verify_sealed_checkpoint
from alpha_lab.research.paper_risk import authorise_simulated_order

class PaperRuntime:
    def __init__(self, path, *, starting_cash="10000", trusted_checkpoint=None,
                 checkpoint_secret=None, check_same_thread=True):
        self.journal = PaperJournal(path, check_same_thread=check_same_thread)
        self.ledger = PaperLedger(starting_cash)
        self.recovery_verified = False
        self.order_ids = set()
        self.events = []
        try:
            if (trusted_checkpoint is None) != (checkpoint_secret is None):
                raise ValueError("checkpoint and independent key must both be supplied: HALT")
            if trusted_checkpoint is not None:
                self.journal_head = verify_sealed_checkpoint(
                    self.journal, trusted_checkpoint, secret=checkpoint_secret)
            else:
                self.journal_head = self.journal.verify()
            for (payload,) in self.journal.connection.execute("SELECT payload FROM events ORDER BY seq"):
                event = json.loads(payload)
                if event.get("type") != "FILL" or event.get("simulated") is not True:
                    raise ValueError("unknown journal event: HALT")
                order_id = event.get("order_id")
                if order_id is not None:
                    if not isinstance(order_id, str) or not order_id or order_id in self.order_ids:
                        raise ValueError("invalid or duplicate order ID: HALT")
                    self.order_ids.add(order_id)
                self.ledger.enable_simulation(operator_approved=True)
                actual = self.ledger.fill(symbol=event["symbol"],side=event["side"],
                    quantity=event["quantity"],reference_mid=event["reference_mid"],
                    executed_price=event["price"],fee=event["fee"])
                for key in ("cash_delta","audit_hash","seq"):
                    if str(actual[key]) != str(event[key]):
                        raise ValueError("replay mismatch: HALT")
                self.events.append(event)
            self.ledger.halt()
            self.recovery_verified = True
        except Exception:
            self.ledger.halt()
            self.journal.close()
            raise

    def execute(self, *, symbol, side, quantity, reference_mid, executed_price, fee,
                quote_timestamp, now, marks, proposed_loss, aggregate_open_risk,
                gross_notional, peak_nav, day_start_nav, operator_approved=False,
                order_id=None, details=None):
        if not self.recovery_verified or self.ledger.halted or operator_approved is not True:
            raise PermissionError("HALT: operator approval and recovered ledger required")
        if not isinstance(order_id, str) or not order_id or len(order_id) > 128:
            self.ledger.halt()
            raise ValueError("mandatory order ID required: HALT")
        if order_id in self.order_ids:
            raise PermissionError("duplicate simulated order ID: HALT")
        if not isinstance(now, datetime) or not isinstance(quote_timestamp, datetime):
            self.ledger.halt()
            raise ValueError("missing quote time: HALT")
        if now.tzinfo is None or quote_timestamp.tzinfo is None or now.utcoffset()!=timedelta(0) or quote_timestamp.utcoffset()!=timedelta(0):
            self.ledger.halt()
            raise ValueError("UTC timestamps required: HALT")
        age = now - quote_timestamp
        fresh = timedelta(0) <= age <= timedelta(seconds=60)
        nav = self.ledger.nav(marks)
        q = number(quantity)
        reducing = side == "SELL" and 0 < q <= self.ledger.positions.get(symbol, 0)
        decision = authorise_simulated_order(nav=nav, initial_nav=self.ledger.starting_cash,
            peak_nav=peak_nav,day_start_nav=day_start_nav,proposed_loss=proposed_loss,
            aggregate_open_risk=aggregate_open_risk,gross_notional=gross_notional,
            proposed_notional=0 if reducing else q * number(executed_price),
            reducing_exposure=reducing,
            data_fresh=fresh,ledger_reconciled=self.recovery_verified,
            operator_enabled=operator_approved)
        if not decision["approved"]:
            self.ledger.halt()
            raise PermissionError("HALT: "+", ".join(decision["reasons"]))
        # Compute a candidate without mutating the authoritative ledger until durable append succeeds.
        import copy
        candidate = copy.deepcopy(self.ledger)
        fill = candidate.fill(symbol=symbol,side=side,quantity=quantity,
            reference_mid=reference_mid,executed_price=executed_price,fee=fee)
        event = {"type":"FILL",**fill}
        event["order_id"] = order_id
        if details is not None:
            event["details"] = details
        try:
            new_head = self.journal.append(event, expected_seq=self.ledger.sequence,
                                           expected_head=self.journal_head)
        except Exception:
            self.ledger.halt()
            raise
        self.journal_head = new_head
        self.ledger = candidate
        self.events.append(event)
        self.order_ids.add(order_id)
        return fill

    def enable(self, *, operator_approved=False):
        if not self.recovery_verified:
            raise PermissionError("HALT: recovery not verified")
        self.ledger.enable_simulation(operator_approved=operator_approved)

    def close(self):
        self.ledger.halt()
        self.journal.close()
