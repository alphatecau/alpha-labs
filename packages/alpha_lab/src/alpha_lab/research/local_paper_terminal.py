"""Single-user paper terminal with Coinbase spot or a synthetic US ETF rehearsal."""
import argparse
import json
import shlex
import sqlite3
import uuid
from contextlib import closing
from decimal import Decimal, DecimalException
from pathlib import Path
from tempfile import TemporaryDirectory

from alpha_lab.research.live_paper_session import LivePaperSession, PaperRejection
from alpha_lab.research.local_etf_fixture import ETF_FIXTURE_MARKET, SyntheticEtfFeed
from alpha_lab.research.local_multiasset_catalogue import catalogue
from alpha_lab.research.local_paper_recovery import JOURNAL_NAME, backup_destination, inspect_journal, publish_verified_file
from alpha_lab.research.paper_market import COINBASE_MARKET, PaperCosts
from alpha_lab.research.paper_market_feed import PaperMarketFeed

DEFAULT_ACCOUNT = "localpaperowner0001"


def backup_journal(session, destination):
    with session.lock:
        if session.fault:
            raise ValueError("paper state requires verified recovery before backup")
        source = Path(session.db.execute("PRAGMA database_list").fetchone()[2]).resolve()
        target = backup_destination(source, destination)
        with TemporaryDirectory(dir=target.parent, prefix=".alpha-backup-") as temporary:
            path = Path(temporary) / "backup.sqlite3"
            with closing(sqlite3.connect(path)) as copy:
                session.db.backup(copy)
                checked = inspect_journal(copy)
                if (checked["events"], checked["head"]) != (session.runtime.ledger.sequence, session.runtime.journal_head):
                    raise ValueError("backup differs from the active journal: HALT")
            publish_verified_file(path, target)
    return {"backup": str(target), "integrity": "PASS", "replay": "PASS",
            "events": checked["events"], "head": checked["head"], "recovery": checked["checkpoint"]}


def _submit(session, parts):
    order_id = None
    if len(parts) >= 2 and parts[-2] == "--id":
        order_id = parts[-1]
        parts = parts[:-2]
    is_limit = parts[0].lower() == "limit"
    if is_limit:
        parts = parts[1:]
    if not parts or parts[0].lower() not in ("buy", "sell"):
        raise ValueError("expected buy or sell")
    side = parts[0].upper()
    expected = 3 + int(side == "BUY") + int(is_limit)
    if len(parts) != expected:
        raise ValueError("expected market, quantity, limit price for a limit order and stop price for a buy")
    if parts[1] not in session.market.symbols:
        raise ValueError("unsupported paper market in this profile")
    if order_id is None:
        raise ValueError("order requires a stable --id. Use new-id and keep it for retries")
    order = {"order_id": order_id, "symbol": parts[1], "side": side, "quantity": parts[2]}
    if side == "BUY":
        order["stop_price"] = parts[-1]
    if is_limit:
        order.update(order_type="LIMIT", limit_price=parts[3])
    try:
        return session.order(order)
    except (PaperRejection, OSError, sqlite3.Error) as exc:
        raise ValueError(f"{exc} (order ID {order_id})") from exc


def command(session, line, *, operator=None):
    parts = shlex.split(line)
    if not parts:
        return None
    verb = parts[0].lower()
    if verb == "help" and len(parts) == 1:
        return {"commands": ["help", "state", "markets", "new-id", "arm", "halt",
                             "buy SYMBOL QUANTITY STOP --id ID", "sell SYMBOL QUANTITY --id ID",
                             "limit buy SYMBOL QUANTITY LIMIT STOP --id ID",
                             "limit sell SYMBOL QUANTITY LIMIT --id ID", "cancel ID",
                             "advance (ETF fixture only)", "backup PATH", "quit"],
                "profile": session.market.name}
    if verb == "markets" and len(parts) == 1:
        return {"catalogue": [dict(symbol=i.symbol, venue=i.venue, asset_class=i.asset_class,
                                    quote_currency=i.quote_currency, data_status=i.data_status,
                                    order_status=i.order_status) for i in catalogue()],
                "paper_products": list(session.market.symbols), "profile": session.market.name}
    if verb == "state" and len(parts) == 1:
        result = session.state()
        if operator is not None:
            result["recovery"].update(operator)
        return result
    if verb == "new-id" and len(parts) == 1:
        return {"order_id": uuid.uuid4().hex}
    if verb == "halt" and len(parts) == 1:
        return session.control("halt")
    if verb == "arm" and len(parts) == 1:
        return session.control("arm", expected_revision=session.state()["risk"]["revision"])
    if verb in ("buy", "sell", "limit"):
        return _submit(session, parts)
    if verb == "cancel" and len(parts) == 2:
        return session.cancel({"order_id": parts[1]})
    if verb == "advance" and len(parts) == 1 and isinstance(session.feed, SyntheticEtfFeed):
        session.feed.advance()
        session.on_market_update()
        return session.state()
    if verb == "backup" and len(parts) == 2:
        receipt = backup_journal(session, parts[1])
        if operator is not None:
            operator["last_verified_backup"] = receipt
        return receipt
    raise ValueError("unknown command or wrong arguments. Type help.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory")
    parser.add_argument("--init", action="store_true", help="explicitly initialise a new working directory")
    parser.add_argument("--account", default=DEFAULT_ACCOUNT)
    parser.add_argument("--synthetic-etfs", action="store_true")
    parser.add_argument("--fee-bps", default="10")
    parser.add_argument("--slippage-bps", default="5")
    args = parser.parse_args(argv)
    try:
        costs = PaperCosts(Decimal(args.fee_bps) / 10000, Decimal(args.slippage_bps) / 10000)
    except (DecimalException, ValueError) as exc:
        parser.error(str(exc))
    fallback = "~/.alpha-labs-etf-fixture" if args.synthetic_etfs else "~/.alpha-labs-paper-working"
    directory = Path(args.directory or fallback).expanduser().resolve()
    journal = directory / JOURNAL_NAME
    if directory == Path("~/.alpha-labs-paper").expanduser().resolve():
        parser.error("the historical journal directory is reserved for read-only recovery")
    try:
        if args.init:
            directory.mkdir(mode=0o700, parents=True)
        elif not journal.is_file():
            raise ValueError("working journal missing. Select the right directory or explicitly use --init")
        elif journal.is_symlink() or journal.stat().st_nlink != 1:
            raise ValueError("working journal must be a standalone SQLite file")
        if args.synthetic_etfs:
            feed = SyntheticEtfFeed()
            session = LivePaperSession(directory, args.account, feed, clock=feed.clock,
                                       market=ETF_FIXTURE_MARKET, costs=costs, migrate=args.init)
        else:
            feed = PaperMarketFeed()
            session = LivePaperSession(directory, args.account, feed, market=COINBASE_MARKET,
                                       costs=costs, migrate=args.init)
    except (ValueError, KeyError, OSError, sqlite3.Error) as exc:
        parser.error(str(exc))
    try:
        if args.synthetic_etfs:
            feed.resume_from(session.runtime.events)
        else:
            feed.start(session.on_market_update)
        operator = {"journal": str(journal), "last_verified_backup": "NOT TESTED"}
        print(f"Alpha Labs · {session.market.name} · simulated USD. Type help.")
        print(f"Journal {operator['journal']} · {session.runtime.ledger.sequence} verified fills · STARTUP HALT")
        while True:
            try:
                line = input("paper> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if line.lower() in ("quit", "exit"):
                break
            try:
                result = command(session, line, operator=operator)
                if result is not None:
                    print(json.dumps(result, indent=2))
            except (ValueError, PaperRejection, OSError, sqlite3.Error) as exc:
                print(f"REJECTED: {exc}")
    finally:
        try:
            if not args.synthetic_etfs:
                feed.close()
        finally:
            session.close()


if __name__ == "__main__":
    main()
