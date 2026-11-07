"""Transactional orchestration: evidence -> decision -> risk -> synthetic order.

Risk and ledger state are recomputed by trusted code, never accepted from agent
output. This single-process boundary still requires service isolation for beta.
"""
from __future__ import annotations

from decimal import Decimal as D
import json
import uuid

from . import committee, ledger
from .brokers import SimulatedBroker
from .contracts import (ContractError, Decision, Forbidden, Mode, Outcome, Proposal,
                        Quote, canonical, digest, identifier, number, serialise, utc)
from .risk import RiskAuthoriser, TERMINAL
from .store import Store


class PaperEngine:
    def __init__(self, store: Store, *, broker=None, risk=None):
        self.store = store
        self.broker = broker or SimulatedBroker()
        self.risk = risk or RiskAuthoriser()
        if not isinstance(self.broker, SimulatedBroker):
            raise PermissionError("only the local simulated broker is allowed")

    def _halt(self, db, principal, account, reason, now):
        account["halted"], account["enabled"], account["halt_reason"] = True, False, reason
        for order in self.store.rows(db, "orders", principal, account["id"]):
            if order["status"] not in TERMINAL:
                order["status"] = "CANCELLED"
                self._save_order(db, principal, account["id"], order)
                self.store.event(db, principal, account["id"], "ORDER_CANCELLED", order, now)
        self.store.save_account(db, principal, account)
        self.store.event(db, principal, account["id"], "HALT", dict(reason=reason), now)

    def control(self, principal, account_id, action, now):
        if action not in {"enable", "suspend", "halt", "clear_halt"}:
            raise ContractError("unsupported account action")
        with self.store.transaction() as db:
            account = self.store.account(db, principal, account_id, write=True)
            utc(now)
            if action == "halt":
                self._halt(db, principal, account, "OPERATOR_HALT", now)
                return
            if action == "enable" and account["halted"]:
                raise Forbidden("HALT requires a separate operator recovery")
            if action == "clear_halt":
                # Does not reset equity anchors, risk limits or enable trading.
                if self.store.rows(db, "positions", principal, account_id):
                    raise Forbidden("review and close open positions before HALT recovery")
                account["halted"], account["halt_reason"] = False, ""
            else:
                account["enabled"] = action == "enable"
            self.store.save_account(db, principal, account)
            self.store.event(db, principal, account_id, "CONTROL", dict(action=action), now)

    def _save_order(self, db, principal, account_id, order):
        db.execute("UPDATE orders SET record=? WHERE tenant=? AND account=? AND key=?",
                   (canonical(order), principal.tenant, account_id, order["key"]))

    def _reconciles(self, db, principal, account_id):
        result = ledger.reconcile(self.store, principal, account_id,
                                  bundle=self.store._bundle(db, principal, account_id))
        return result["ok"]

    def cycle(self, principal, proposal: Proposal, quote: Quote, now: str):
        request_hash = digest(proposal)
        with self.store.transaction() as db:
            account = self.store.account(db, principal, proposal.account_id, write=True)
            previous = db.execute("SELECT request_hash,record FROM orders WHERE tenant=? AND account=? AND key=?",
                                  (principal.tenant, proposal.account_id, proposal.idempotency_key)).fetchone()
            if previous:
                if previous[0] != request_hash:
                    raise ContractError("idempotency key conflicts with original proposal")
                return json.loads(previous[1])
            if not self._reconciles(db, principal, account["id"]):
                self._halt(db, principal, account, "RECONCILIATION_FAILED", now)
                decision = Decision(Outcome.HALT, ("RECONCILIATION_FAILED",), request_hash, digest(quote), ())
                self.store.event(db, principal, account["id"], "DECISION", decision, now)
                return dict(decision=serialise(decision), status="REJECTED", order_id=None)
            db.execute("SAVEPOINT market_update")
            try:
                quote.check(now)
                if quote.currency != account["currency"] or quote.instrument != proposal.instrument:
                    raise ContractError("quote/account identity mismatch")
                ledger.save_quote(self.store, db, principal, account, quote)
                positions = ledger.mark(self.store, db, principal, account, now, self.risk.costs)
                db.execute("RELEASE market_update")
            except (ContractError, KeyError):
                db.execute("ROLLBACK TO market_update")
                db.execute("RELEASE market_update")
                account = self.store.account(db, principal, proposal.account_id, write=True)
                self._halt(db, principal, account, "DATA_INVALID_OR_STALE", now)
                decision = Decision(Outcome.HALT, ("DATA_INVALID_OR_STALE",), request_hash, digest(quote), ())
                self.store.event(db, principal, account["id"], "DECISION", decision, now)
                return dict(decision=serialise(decision), status="REJECTED", order_id=None)
            risk_stop = ledger.suspension(account)
            if risk_stop:
                self._halt(db, principal, account, risk_stop, now)
            assessments = committee.assess(proposal, quote, now, exposure=str(sum(
                (D(p["quantity"])*D(p["mark"]) for p in positions), D(0))))
            outcome, reasons = committee.gate(proposal, quote)
            fee, loss = D(0), D(0)
            if account["halted"] or proposal.direction == Outcome.HALT:
                self._halt(db, principal, account, account["halt_reason"] or "PROPOSAL_HALT", now)
                outcome, reasons = Outcome.HALT, (account["halt_reason"],)
            elif outcome == Outcome.LONG:
                risk_reasons, fee, loss = self.risk.evaluate(
                    proposal, quote, account, positions,
                    self.store.rows(db, "orders", principal, account["id"]), now,
                    broker_connected=self.broker.health())
                if risk_reasons:
                    outcome, reasons = Outcome.HALT, risk_reasons
                    # Conservative prototype policy: every risk HALT persists.
                    self._halt(db, principal, account, reasons[0], now)
            decision = Decision(outcome, reasons, request_hash, digest(quote), assessments,
                                fee, loss, outcome == Outcome.LONG)
            self.store.event(db, principal, account["id"], "DECISION", decision, now)
            self.store.save_account(db, principal, account)
            if outcome != Outcome.LONG:
                return dict(decision=serialise(decision), status="REJECTED", order_id=None)
            order = dict(schema="alpha-labs.order.v1", id=uuid.uuid4().hex, account=account["id"],
                         key=proposal.idempotency_key, proposal=serialise(proposal), decision=serialise(decision),
                         quantity=str(proposal.quantity), filled_quantity="0", fills=[], side="BUY",
                         status="ACKNOWLEDGED", created_at=now, quote=serialise(quote),
                         broker="local-simulation", simulated=True, live_trading_authorised=False)
            db.execute("INSERT INTO orders VALUES(?,?,?,?,?)",
                       (principal.tenant, account["id"], order["key"], request_hash, canonical(order)))
            self.store.event(db, principal, account["id"], "ORDER_ACKNOWLEDGED", order, now)
            return order

    def fill(self, principal, account_id, key, quote: Quote, now: str, *, quantity=None,
             fill_id=None):
        # Explicit fill IDs prevent duplicate partial-fill delivery. Full completion
        # is also idempotent through the durable terminal order state.
        if quantity is not None and fill_id is None:
            raise ContractError("partial fills require an explicit delivery identifier")
        fill_id = identifier(fill_id or "completion")
        with self.store.transaction() as db:
            account = self.store.account(db, principal, account_id, write=True)
            row = db.execute("SELECT record FROM orders WHERE tenant=? AND account=? AND key=?",
                             (principal.tenant, account_id, key)).fetchone()
            if row is None:
                raise Forbidden("order unavailable")
            order = json.loads(row[0])
            previous_fill = next((f for f in order["fills"] if f.get("fill_id") == fill_id), None)
            if previous_fill:
                if quantity is not None and D(previous_fill["quantity"]) != number(quantity, positive=True):
                    raise ContractError("fill idempotency conflict")
                return order
            if order["status"] in TERMINAL:
                return order
            if not self._reconciles(db, principal, account_id):
                self._halt(db, principal, account, "RECONCILIATION_FAILED", now)
                order["status"] = "CANCELLED"
                self._save_order(db, principal, account_id, order)
                return order
            remaining = D(order["quantity"])-D(order["filled_quantity"])
            quantity = remaining if quantity is None else number(quantity, positive=True)
            if quantity > remaining:
                raise ContractError("fill exceeds remaining quantity")
            db.execute("SAVEPOINT fill_attempt")
            try:
                quote.check(now)
                if (quote.instrument != order["proposal"]["instrument"]
                        or quote.currency != account["currency"] or not quote.synthetic
                        or quote.venue != "synthetic"):
                    raise ContractError("fill quote identity mismatch")
                ledger.save_quote(self.store, db, principal, account, quote)
                positions = ledger.mark(self.store, db, principal, account, now, self.risk.costs)
                original = Proposal(**order["proposal"])
                # Re-authorise the entire unfilled remainder at current economics.
                pending_proposal = Proposal(**{**order["proposal"], "quantity": str(remaining)})
                other_orders = [o for o in self.store.rows(db, "orders", principal, account_id)
                                if o["id"] != order["id"]]
                other_positions = [p for p in positions if p["instrument"] != original.instrument]
                # Existing partial inventory is included in equity/exposure/risk checks.
                reasons, _, new_loss = self.risk.evaluate(
                    pending_proposal, quote, account, other_positions, other_orders, now,
                    broker_connected=self.broker.health())
                own_position = next((p for p in positions if p["instrument"] == original.instrument), None)
                if own_position:
                    limits = account["limits"]
                    equity = D(account["last_equity"])
                    if D(own_position["planned_loss"])+new_loss > equity*D(limits["position_loss"]):
                        reasons += ("PARTIAL_POSITION_LOSS_LIMIT",)
                    exposure = sum((D(p["quantity"])*D(p["mark"]) for p in positions), D(0))
                    if exposure+remaining*self.risk.costs.price(quote, "BUY") > equity*D(limits["total_exposure"]):
                        reasons += ("PARTIAL_EXPOSURE_LIMIT",)
                    if (D(own_position["quantity"])*D(own_position["mark"])
                            + remaining*self.risk.costs.price(quote, "BUY") > equity*D(limits["concentration"])):
                        reasons += ("PARTIAL_CONCENTRATION_LIMIT",)
                    stop_risk = sum((D(p["planned_loss"]) for p in positions), D(0))
                    if stop_risk+new_loss > equity*D(limits["aggregate_stop_risk"]):
                        reasons += ("PARTIAL_AGGREGATE_STOP_RISK_LIMIT",)
                entry = D(order["quote"]["ask"])
                if abs(quote.ask-entry)/entry > D(account["limits"]["price_deviation"]):
                    reasons += ("ENTRY_PRICE_DEVIATION",)
                if reasons:
                    order["status"], order["rejection_reasons"] = "REJECTED", list(reasons)
                    self._save_order(db, principal, account_id, order)
                    self.store.event(db, principal, account_id, "ORDER_REJECTED", order, now)
                    self._halt(db, principal, account, reasons[0], now)
                else:
                    ledger.fill(self.store, db, principal, account, order, quote, quantity,
                                "BUY", now, self.risk.costs)
                    order["fills"][-1]["fill_id"] = fill_id
                    ledger.mark(self.store, db, principal, account, now, self.risk.costs)
                    if reason := ledger.suspension(account):
                        self._save_order(db, principal, account_id, order)
                        self._halt(db, principal, account, reason, now)
                        if order["status"] not in TERMINAL:
                            order["status"] = "CANCELLED"
                db.execute("RELEASE fill_attempt")
            except (ContractError, KeyError):
                db.execute("ROLLBACK TO fill_attempt")
                db.execute("RELEASE fill_attempt")
                account = self.store.account(db, principal, account_id, write=True)
                order = json.loads(row[0])
                self._halt(db, principal, account, "FILL_DATA_INVALID_OR_STALE", now)
                order["status"] = "CANCELLED"
            self._save_order(db, principal, account_id, order)
            self.store.save_account(db, principal, account)
            return order

    def cancel(self, principal, account_id, key, now):
        with self.store.transaction() as db:
            self.store.account(db, principal, account_id, write=True)
            row = db.execute("SELECT record FROM orders WHERE tenant=? AND account=? AND key=?",
                             (principal.tenant, account_id, key)).fetchone()
            if not row:
                raise Forbidden("order unavailable")
            order = json.loads(row[0])
            if order["status"] not in TERMINAL:
                order["status"] = "CANCELLED"
                self._save_order(db, principal, account_id, order)
                self.store.event(db, principal, account_id, "ORDER_CANCELLED", order, now)
            return order

    def close_position(self, principal, account_id, quote: Quote, now: str, *, key: str):
        # An operator may reduce existing risk while HALTed. This never opens a short.
        identifier(key)
        with self.store.transaction() as db:
            account = self.store.account(db, principal, account_id, write=True)
            if not self._reconciles(db, principal, account_id):
                self._halt(db, principal, account, "RECONCILIATION_FAILED", now)
                return dict(status="REJECTED")
            if account["mode"] != Mode.SIMULATION or not self.broker.health():
                self._halt(db, principal, account, "EXIT_MODE_OR_CONNECTIVITY_BLOCKED", now)
                return dict(status="REJECTED")
            previous = db.execute("SELECT record FROM orders WHERE tenant=? AND account=? AND key=?",
                                  (principal.tenant, account_id, key)).fetchone()
            if previous:
                old = json.loads(previous[0])
                if old["side"] != "SELL" or old["proposal"]["instrument"] != quote.instrument:
                    raise ContractError("exit idempotency conflict")
                return old
            quote.check(now)
            if (not quote.synthetic or quote.venue != "synthetic"
                    or quote.currency != account["currency"] or quote.instrument != "TEST/AUD"):
                raise ContractError("exit quote not a supported fixture")
            ledger.save_quote(self.store, db, principal, account, quote)
            positions = ledger.mark(self.store, db, principal, account, now, self.risk.costs)
            position = next((p for p in positions if p["instrument"] == quote.instrument), None)
            if position is None:
                raise ContractError("no position to close")
            for pending in self.store.rows(db, "orders", principal, account_id):
                if pending["status"] not in TERMINAL:
                    pending["status"] = "CANCELLED"
                    self._save_order(db, principal, account_id, pending)
                    self.store.event(db, principal, account_id, "ORDER_CANCELLED", pending, now)
            qty = D(position["quantity"])
            exit_reasons = self.risk.evaluate_exit(quote, account, position, now,
                                                  broker_connected=self.broker.health())
            if exit_reasons:
                self._halt(db, principal, account, exit_reasons[0], now)
                return dict(status="REJECTED")
            order = dict(id=uuid.uuid4().hex, key=key, proposal=dict(instrument=quote.instrument),
                         side="SELL", quantity=str(qty), filled_quantity="0", status="ACKNOWLEDGED",
                         fills=[], simulated=True, live_trading_authorised=False, created_at=now,
                         authorisation="DETERMINISTIC_REDUCE_ONLY")
            db.execute("INSERT INTO orders VALUES(?,?,?,?,?)",
                       (principal.tenant, account_id, key, digest(dict(side="SELL", instrument=quote.instrument)),
                        canonical(order)))
            ledger.fill(self.store, db, principal, account, order, quote, qty, "SELL", now, self.risk.costs)
            ledger.mark(self.store, db, principal, account, now, self.risk.costs)
            if reason := ledger.suspension(account):
                self._halt(db, principal, account, reason, now)
            self._save_order(db, principal, account_id, order)
            self.store.save_account(db, principal, account)
            return order

    def autonomous_cycle(self, principal, proposal, quote, now):
        """One bounded cycle, including fill and deterministic stop management."""
        snapshot = self.store.snapshot(principal, proposal.account_id)
        position = next((p for p in snapshot["positions"] if p["instrument"] == quote.instrument), None)
        if position:
            quote.check(now)
            if quote.bid <= D(position["stop_price"]) or proposal.direction == Outcome.FLAT:
                return self.close_position(principal, proposal.account_id, quote, now,
                                           key="stop-"+proposal.idempotency_key)
        order = self.cycle(principal, proposal, quote, now)
        if order["status"] in {"ACKNOWLEDGED", "PARTIALLY_FILLED"}:
            return self.fill(principal, proposal.account_id, order["key"], quote, now)
        return order

    def recover(self, principal, account_id, now):
        # No replayed side effects: unresolved orders are cancelled and account HALTed.
        result = ledger.reconcile(self.store, principal, account_id)
        with self.store.transaction() as db:
            account = self.store.account(db, principal, account_id, write=True)
            pending = any(o["status"] not in TERMINAL
                          for o in self.store.rows(db, "orders", principal, account_id))
            if pending or not result["ok"]:
                self._halt(db, principal, account, "RECOVERY_REVIEW_REQUIRED", now)
            self.store.event(db, principal, account_id, "RECOVERY", result, now)
        return result
