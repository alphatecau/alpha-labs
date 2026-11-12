"""Free single-user local paper terminal. No HTTP listener, broker keys or live orders.

Run: python -m alpha_lab.research.local_paper_terminal --directory ~/.alpha-labs-paper
Commands: help, state, markets, arm, halt, buy SYMBOL QTY STOP, sell SYMBOL QTY,
          backup PATH, quit. Existing Coinbase spot session remains BTC/ETH/SOL only.
"""
import argparse
import json
import os
import shlex
import sqlite3
import uuid
from pathlib import Path

from alpha_lab.research.coinbase_paper_book import PRODUCTS
from alpha_lab.research.live_paper_session import LivePaperSession, PaperRejection
from alpha_lab.research.paper_market_feed import PaperMarketFeed
from alpha_lab.research.local_multiasset_catalogue import catalogue

DEFAULT_ACCOUNT = "localpaperowner0001"


def command(session, line):
    parts = shlex.split(line)
    if not parts:
        return None
    verb = parts[0].lower()
    if verb == "help" and len(parts) == 1:
        return {"commands": ["help", "state", "markets", "arm", "halt",
                             "buy BTC-USD 0.001 10000", "sell BTC-USD 0.001",
                             "backup /safe/path/paper-backup.sqlite3", "quit"],
                "notice": "Only BTC-USD, ETH-USD and SOL-USD may be simulated; other catalogue entries are disabled."}
    if verb == "markets" and len(parts) == 1:
        return {"catalogue": [dict(symbol=i.symbol, venue=i.venue,
                                    asset_class=i.asset_class,
                                    data_status=i.data_status,
                                    order_status=i.order_status)
                              for i in catalogue()],
                "paper_products": list(PRODUCTS)}
    if verb == "state" and len(parts) == 1:
        return session.state()
    if verb == "halt" and len(parts) == 1:
        return session.control("halt")
    if verb == "arm" and len(parts) == 1:
        state = session.state()
        return session.control("arm", expected_revision=state["risk"]["revision"])
    if verb in ("buy", "sell") and len(parts) in (3, 4):
        side = verb.upper()
        if (side == "BUY" and len(parts) != 4) or (side == "SELL" and len(parts) != 3):
            raise ValueError("buy requires a stop; sell does not")
        if parts[1] not in PRODUCTS:
            raise ValueError("unsupported paper market: catalogue listing does not enable orders")
        order = {"order_id": uuid.uuid4().hex, "symbol": parts[1],
                 "side": side, "quantity": parts[2]}
        if side == "BUY":
            order["stop_price"] = parts[3]
        return session.order(order)
    if verb == "backup" and len(parts) == 2:
        target = Path(parts[1]).expanduser().resolve()
        source = Path(session.runtime.journal.connection.execute("PRAGMA database_list").fetchone()[2]).resolve()
        if target == source or target.exists() or target.is_relative_to(source.parent):
            raise ValueError("backup must be a new file in a separate directory")
        if not target.parent.is_dir():
            raise ValueError("backup destination directory does not exist")
        with session.lock:
            with sqlite3.connect(target) as destination:
                session.db.backup(destination)
            os.chmod(target, 0o600)
        return {"backup": str(target), "note": "Copy offline; separately protect and verify checkpoint before trusting restoration"}
    raise ValueError("unknown command or wrong arguments; type help")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Alpha Labs local paper terminal (simulation only)")
    parser.add_argument("--directory", default="~/.alpha-labs-paper")
    parser.add_argument("--account", default=DEFAULT_ACCOUNT)
    args = parser.parse_args(argv)
    directory = Path(args.directory).expanduser().resolve()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    feed = PaperMarketFeed()
    session = LivePaperSession(directory, args.account, feed)
    try:
        feed.start(session.on_market_update)
        print("ALPHA LABS — LOCAL PAPER ONLY. No broker orders. Type help.")
        while True:
            try:
                line = input("paper> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if line.lower() in ("quit", "exit"):
                break
            try:
                result = command(session, line)
                if result is not None:
                    print(json.dumps(result, indent=2, default=str))
            except (ValueError, PaperRejection, OSError, sqlite3.Error) as exc:
                print(f"REJECTED: {exc}")
    finally:
        # Stop feed before closing the journal; no asynchronous ledger writes after close.
        try:
            feed.close()
        finally:
            session.close()


if __name__ == "__main__":
    main()
