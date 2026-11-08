"""Offline paper runtime: replay journal before admitting new simulated fills.

No HTTP server, broker, external orders, background scheduler or credential access.
"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
from alpha_lab.research.paper_simulator import PaperLedger, number
from alpha_lab.research.paper_journal import PaperJournal
from alpha_lab.research.paper_risk import authorise_simulated_order

class PaperRuntime:
    def __init__(self, path, *, starting_cash="10000"):
        self.journal = PaperJournal(path)
        self.ledger = PaperLedger(starting_cash)
        self.recovery_verified = False
        self._seen_ids = set()
        try:
            self.journal.verify()
            for (payload,) in self.journal.connection.execute("SELECT payload FROM events ORDER BY seq"):
                event = json.loads(payload)
                request_id = event.get("request_id")
                if not isinstance(request_id, str) or not request_id or request_id in self._seen_ids:
                    raise ValueError("invalid or duplicate request id: HALT")
                self._seen_ids.add(request_id)
                if event.get("type") != "FILL" or event.get("simulated") is not True:
                    raise ValueError("unknown journal event: HALT")
                self.ledger.enable_simulation(operator_approved=True)
                actual = self.ledger.fill(symbol=event["symbol"],side=event["side"],
                    quantity=event["quantity"],reference_mid=event["reference_mid"],
                    executed_price=event["price"],fee=event["fee"])
                for key in ("cash_delta","audit_hash","seq"):
                    if str(actual[key]) != str(event[key]):
                        raise ValueError("replay mismatch: HALT")
            self.ledger.halt()
            self.recovery_verified = True
        except Exception:
            self.ledger.halt()
            self.journal.close()
            raise

    def execute(self, *, symbol, side, quantity, reference_mid, executed_price, fee,
                quote_timestamp, now, marks, proposed_loss, aggregate_open_risk,
                gross_notional, peak_nav, day_start_nav, operator_approved=False,
                request_id=None, authoritative_risk_verified=False):
        if not self.recovery_verified or self.ledger.halted or operator_approved is not True:
            raise PermissionError("HALT: operator approval and recovered ledger required")
        if authoritative_risk_verified is not True:
            self.ledger.halt()
            raise PermissionError("HALT: independently authoritative risk inputs unavailable")
        if not isinstance(request_id, str) or not request_id or len(request_id) > 128 or request_id in self._seen_ids:
            self.ledger.halt()
            raise PermissionError("HALT: invalid or duplicate request id")
        if not isinstance(now, datetime) or not isinstance(quote_timestamp, datetime):
            self.ledger.halt()
            raise ValueError("missing quote time: HALT")
        if now.tzinfo is None or quote_timestamp.tzinfo is None or now.utcoffset()!=timedelta(0) or quote_timestamp.utcoffset()!=timedelta(0):
            self.ledger.halt()
            raise ValueError("UTC timestamps required: HALT")
        age = now - quote_timestamp
        fresh = timedelta(0) <= age <= timedelta(seconds=60)
        nav = self.ledger.nav(marks)
        decision = authorise_simulated_order(nav=nav, initial_nav=self.ledger.starting_cash,
            peak_nav=peak_nav,day_start_nav=day_start_nav,proposed_loss=proposed_loss,
            aggregate_open_risk=aggregate_open_risk,gross_notional=gross_notional,
            proposed_notional=number(quantity)*number(executed_price),
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
        event = {"type":"FILL","request_id":request_id,**fill}
        self.journal.append(event)
        self.ledger = candidate
        self._seen_ids.add(request_id)
        return fill

    def enable(self, *, operator_approved=False):
        if not self.recovery_verified:
            raise PermissionError("HALT: recovery not verified")
        self.ledger.enable_simulation(operator_approved=operator_approved)

    def close(self):
        self.ledger.halt()
        self.journal.close()
