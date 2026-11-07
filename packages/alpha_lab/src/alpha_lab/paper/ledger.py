"""Deterministic cash/long-inventory accounting for synthetic fills only."""
from __future__ import annotations

from decimal import Decimal as D
import json

from .contracts import ContractError, Quote, canonical, digest, utc
from .risk import Limits


def save_quote(store, db, principal, account, quote: Quote):
    old = db.execute("SELECT record FROM quotes WHERE tenant=? AND account=? AND instrument=?",
                     (principal.tenant, account["id"], quote.instrument)).fetchone()
    if old:
        previous = Quote(**json.loads(old[0]))
        if (utc(quote.event_time) < utc(previous.event_time)
                or utc(quote.received_time) < utc(previous.received_time)
                or quote.event_time == previous.event_time and digest(quote) != digest(previous)):
            raise ContractError("replayed, conflicting or reordered quote")
    db.execute("INSERT OR REPLACE INTO quotes VALUES(?,?,?,?)",
               (principal.tenant, account["id"], quote.instrument, canonical(quote)))


def mark(store, db, principal, account, now, costs):
    if utc(now) < utc(account["last_time"]):
        raise ContractError("clock regression")
    moment = utc(now)
    day, week = moment.date().isoformat(), moment.strftime("%G-W%V")
    if day != account["day"]:
        account["day_start"], account["day"] = account["last_equity"], day
    if week != account["week"]:
        account["week_start"], account["week"] = account["last_equity"], week
    positions = store.rows(db, "positions", principal, account["id"])
    quotes = {q["instrument"]: Quote(**q) for q in store.rows(db, "quotes", principal, account["id"])}
    equity = D(account["cash"])
    for position in positions:
        q = quotes[position["instrument"]]
        q.check(now)
        price = costs.price(q, "SELL") * (1-costs.fee_bps/10000)
        position["mark"] = str(price)
        position["unrealised_pnl"] = str(D(position["quantity"])*price-D(position["basis"]))
        equity += D(position["quantity"])*price
        db.execute("UPDATE positions SET record=? WHERE tenant=? AND account=? AND instrument=?",
                   (canonical(position), principal.tenant, account["id"], position["instrument"]))
    account["last_equity"] = str(equity)
    account["peak_equity"] = str(max(equity, D(account["peak_equity"])))
    account["last_time"] = now
    return positions


def suspension(account):
    limits = Limits(**account["limits"])
    equity = D(account["last_equity"])
    if equity <= D(account["peak_equity"])*(1-limits.drawdown):
        return "DRAWDOWN_SUSPENSION"
    if equity <= D(account["day_start"])*(1-limits.daily_loss):
        return "DAILY_LOSS_SUSPENSION"
    if equity <= D(account["week_start"])*(1-limits.weekly_loss):
        return "WEEKLY_LOSS_SUSPENSION"
    return ""


def fill(store, db, principal, account, order, quote, quantity, side, now, costs):
    """Caller has already re-authorised within this same transaction."""
    price = costs.price(quote, side)
    fee = costs.fee(quantity, price)
    existing = db.execute("SELECT record FROM positions WHERE tenant=? AND account=? AND instrument=?",
                          (principal.tenant, account["id"], quote.instrument)).fetchone()
    position = json.loads(existing[0]) if existing else None
    if side == "BUY":
        cost = quantity*price+fee
        if cost > D(account["cash"]):
            raise ContractError("insufficient buying power at fill")
        account["cash"] = str(D(account["cash"])-cost)
        position = position or dict(instrument=quote.instrument, quantity="0", basis="0",
                                    stop_price=order["proposal"]["stop_price"], planned_loss="0",
                                    strategy_id=order["proposal"]["strategy_id"], mark="0")
        position["quantity"] = str(D(position["quantity"])+quantity)
        position["basis"] = str(D(position["basis"])+cost)
        position["planned_loss"] = str(D(position["planned_loss"])+costs.planned_loss(
            quantity, price, D(position["stop_price"])))
    else:
        if position is None or quantity > D(position["quantity"]):
            raise ContractError("cannot sell nonexistent long inventory")
        previous_quantity = D(position["quantity"])
        basis = D(position["basis"])*quantity/previous_quantity
        proceeds = quantity*price-fee
        account["cash"] = str(D(account["cash"])+proceeds)
        account["realised_pnl"] = str(D(account["realised_pnl"])+proceeds-basis)
        position["quantity"] = str(previous_quantity-quantity)
        position["basis"] = str(D(position["basis"])-basis)
        position["planned_loss"] = str(D(position["planned_loss"])*(1-quantity/previous_quantity))
    account["fees"] = str(D(account["fees"])+fee)
    if D(position["quantity"]) == 0:
        db.execute("DELETE FROM positions WHERE tenant=? AND account=? AND instrument=?",
                   (principal.tenant, account["id"], quote.instrument))
    else:
        db.execute("INSERT OR REPLACE INTO positions VALUES(?,?,?,?)",
                   (principal.tenant, account["id"], quote.instrument, canonical(position)))
    filled = D(order["filled_quantity"])+quantity
    order["filled_quantity"] = str(filled)
    order["status"] = "FILLED" if filled == D(order["quantity"]) else "PARTIALLY_FILLED"
    order["fills"].append(dict(quantity=str(quantity), price=str(price), fee=str(fee), timestamp=now,
                               quote_hash=digest(quote), simulated=True))
    store.event(db, principal, account["id"], "FILL", dict(
        order_id=order["id"], instrument=quote.instrument, side=side,
        quantity=str(quantity), price=str(price), fee=str(fee), simulated=True), now)


def reconcile(store, principal, account_id, *, bundle=None):
    """Independent event-based cash, fees, basis and realised-P&L reconstruction."""
    snapshot, events, audit_ok = bundle or store.bundle(principal, account_id)
    if not audit_ok:
        return dict(ok=False, reasons=["AUDIT_CHAIN_MISMATCH"], simulated=True)
    cash, fees, realised, inventory = D(0), D(0), D(0), {}
    for event in events:
        item = event["payload"]
        if event["kind"] == "ACCOUNT_CREATED":
            cash = D(item["initial_cash"])
        if event["kind"] != "FILL":
            continue
        qty, price, fee = (D(item[k]) for k in ("quantity", "price", "fee"))
        symbol = item["instrument"]
        held, basis = inventory.get(symbol, (D(0), D(0)))
        fees += fee
        if item["side"] == "BUY":
            cash -= qty*price+fee
            inventory[symbol] = (held+qty, basis+qty*price+fee)
        else:
            if held < qty or held <= 0:
                return dict(ok=False, reasons=["NEGATIVE_REPLAY_INVENTORY"])
            allocated = basis*qty/held
            cash += qty*price-fee
            realised += qty*price-fee-allocated
            inventory[symbol] = (held-qty, basis-allocated)
    account = snapshot["account"]
    actual = {p["instrument"]: (D(p["quantity"]), D(p["basis"])) for p in snapshot["positions"]}
    expected = {k: v for k, v in inventory.items() if v[0] != 0}
    reasons = []
    if cash != D(account["cash"]):
        reasons.append("CASH_MISMATCH")
    if fees != D(account["fees"]) or realised != D(account["realised_pnl"]):
        reasons.append("PNL_OR_FEE_MISMATCH")
    if expected != actual:
        reasons.append("INVENTORY_OR_BASIS_MISMATCH")
    if not audit_ok:
        reasons.append("AUDIT_CHAIN_MISMATCH")
    return dict(ok=not reasons, reasons=reasons, replay_cash=str(cash), replay_fees=str(fees),
                replay_realised_pnl=str(realised), simulated=True)
