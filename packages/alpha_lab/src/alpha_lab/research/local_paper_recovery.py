"""Read-only journal verification, backup and recovery into a new working copy."""
import argparse
import fcntl
import json
import os
import re
import shutil
import sqlite3
import stat
from contextlib import ExitStack, closing, suppress
from decimal import Decimal, DecimalException
from pathlib import Path
from tempfile import TemporaryDirectory

from alpha_lab.research.live_paper_session import LivePaperSession
from alpha_lab.research.local_etf_fixture import ETF_FIXTURE_MARKET, SyntheticEtfFeed
from alpha_lab.research.paper_accounting import reconcile_paper_pnl
from alpha_lab.research.paper_journal import LOCAL_TABLES, journal_tables
from alpha_lab.research.paper_market import COINBASE_MARKET, DEFAULT_COSTS, PaperCosts
from alpha_lab.research.paper_market_feed import PaperMarketFeed
from alpha_lab.research.paper_runtime import replay_paper_events

JOURNAL_NAME = "alpha-paper.sqlite3"
EMPTY_HEAD = "0" * 64


def _fingerprint(status):
    return (status.st_dev, status.st_ino, status.st_size, status.st_mtime_ns, status.st_ctime_ns)


def _require_no_sidecars(path):
    if any(os.path.lexists(str(path) + extension) for extension in ("-wal", "-shm", "-journal")):
        raise ValueError("SQLite sidecar present. Close the writer and verify a clean snapshot: HALT")


def snapshot_read_only(path, target):
    """Copy a stable, stopped SQLite file without opening the source in SQLite."""
    source = Path(path).expanduser().resolve(strict=True)
    with ExitStack() as stack:
        for lock in (source.parent / "alpha-paper.lock", source.with_name(source.name + ".writer.lock")):
            try:
                handle = stack.enter_context(lock.open("rb"))
            except FileNotFoundError:
                continue
            try:
                fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError("paper journal has an active writer. Quit the paper terminal first") from exc
        before = source.stat()
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("journal must be an existing regular file")
        _require_no_sidecars(source)
        with source.open("rb") as handle, Path(target).open("xb") as output:
            if _fingerprint(os.fstat(handle.fileno())) != _fingerprint(before):
                raise ValueError("journal changed while opening it: HALT")
            shutil.copyfileobj(handle, output)
            if _fingerprint(os.fstat(handle.fileno())) != _fingerprint(before):
                raise ValueError("journal changed during verification: HALT")
        _require_no_sidecars(source)
        if _fingerprint(source.stat()) != _fingerprint(before):
            raise ValueError("journal path changed during verification: HALT")
    return source, (before.st_dev, before.st_ino)


def inspect_journal(connection):
    """Check SQLite structure, the event chain and independent accounting."""
    if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise ValueError("SQLite integrity check failed: HALT")
    tables = journal_tables(connection)
    if "events" not in tables:
        raise ValueError("paper events table missing: HALT")
    ledger, events, _, head = replay_paper_events(connection)
    marks = {fill["symbol"]: fill["price"] for fill in events}
    accounting = reconcile_paper_pnl(ledger.fills, marks, starting_cash=ledger.starting_cash)
    if (accounting["cash"] != ledger.cash or accounting["positions"] != ledger.positions
            or accounting["nav"] != ledger.nav(marks)):
        raise ValueError("independent paper accounting does not match the ledger: HALT")
    account = None
    enabled = None
    if "paper_guard" in tables:
        rows = connection.execute("SELECT id,account,enabled FROM paper_guard").fetchall()
        if (len(rows) != 1 or rows[0][0] != 1 or not isinstance(rows[0][1], str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{16,80}", rows[0][1]) or rows[0][2] not in (0, 1)):
            raise ValueError("paper owner or guard record is invalid: HALT")
        _, account, enabled = rows[0]
    profile = None
    if "paper_configuration" in tables:
        rows = connection.execute("SELECT id,configuration FROM paper_configuration").fetchall()
        if len(rows) != 1 or rows[0][0] != 1:
            raise ValueError("paper configuration record is invalid: HALT")
        profile = json.loads(rows[0][1])
        if not isinstance(profile, dict):
            raise ValueError("paper configuration record is invalid: HALT")
    return {
        "integrity": "PASS", "hash_chain": "PASS", "independent_replay": "PASS",
        "events": ledger.sequence, "head": head, "account": account, "profile": profile,
        "schema": "CURRENT" if LOCAL_TABLES <= tables else "LEGACY",
        "stored_armed_flag": enabled, "replay_halted": ledger.halted,
        "checkpoint": "AUTHORITY_REQUIRED" if "paper_state_sequence" in tables else "LOCAL_UNANCHORED",
        "cash_usd": str(accounting["cash"]), "fees_usd": str(accounting["fees"]),
        "realised_usd": str(accounting["realised"]), "nav_usd": str(accounting["nav"]),
        "unrealised_usd": str(accounting["unrealised"]), "valuation": "OFFLINE_LAST_FILL_MARKS",
        "positions": {symbol: str(qty) for symbol, qty in ledger.positions.items() if qty},
    }


def inspect_snapshot(path):
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro&immutable=1", uri=True)) as connection:
        return inspect_journal(connection)


def _verify_pair(journal, backup, scratch, *, minimum_events, expected_sequence=None, expected_head=None):
    if (expected_sequence is None) != (expected_head is None):
        raise ValueError("supply both independently held sequence and head")
    if expected_head is not None and (expected_sequence < 0 or not re.fullmatch(r"[0-9a-f]{64}", expected_head)):
        raise ValueError("invalid independently held checkpoint")
    journal_copy, backup_copy = scratch / "journal.sqlite3", scratch / "backup.sqlite3"
    journal_path, journal_identity = snapshot_read_only(journal, journal_copy)
    backup_path, backup_identity = snapshot_read_only(backup, backup_copy)
    if journal_identity == backup_identity:
        raise ValueError("journal and backup select the same file")
    original = inspect_snapshot(journal_copy)
    saved = inspect_snapshot(backup_copy)
    if original["events"] < minimum_events:
        raise ValueError("selected journal has fewer than the expected minimum fills. Verify its path")
    if (saved["account"] != original["account"] or saved["events"] > original["events"]
            or saved["profile"] is not None and saved["profile"] != original["profile"]):
        raise ValueError("backup owner, profile or journal sequence disagrees: HALT")
    if saved["events"]:
        with closing(sqlite3.connect(journal_copy.as_uri() + "?mode=ro&immutable=1", uri=True)) as connection:
            prefix, = connection.execute("SELECT digest FROM events WHERE seq=?", (saved["events"],)).fetchone()
    else:
        prefix = EMPTY_HEAD
    if prefix != saved["head"]:
        raise ValueError("backup does not share the selected journal history: HALT")
    if expected_head is not None and (original["events"], original["head"]) != (expected_sequence, expected_head):
        raise ValueError("journal disagrees with the supplied independent checkpoint: HALT")
    return {
        "status": "PASS", "journal": {"path": str(journal_path), **original},
        "backup": {"path": str(backup_path), **saved},
        "backup_relationship": "EXACT_FILL_HISTORY" if saved["events"] == original["events"] else "VERIFIED_PREFIX",
        "independent_fill_checkpoint": "MATCH" if expected_head is not None else "NOT TESTED",
    }, journal_copy


def verify_pair(journal, backup, *, minimum_events=0, expected_sequence=None, expected_head=None):
    with TemporaryDirectory(prefix="alpha-paper-verify-") as temporary:
        result, _ = _verify_pair(journal, backup, Path(temporary), minimum_events=minimum_events,
                                 expected_sequence=expected_sequence, expected_head=expected_head)
    return result


def backup_destination(source, destination):
    target = Path(destination).expanduser()
    target = target.parent.resolve() / target.name
    if os.path.lexists(target) or target.is_relative_to(source.parent) or not target.parent.is_dir():
        raise ValueError("backup must be a new file in an existing, separate directory")
    return target


def publish_verified_file(copy, target):
    """Publish a verified file staged in the destination filesystem."""
    copy.chmod(0o600)
    with copy.open("rb") as handle:
        os.fsync(handle.fileno())
    # An interruption before rename can leave only the empty, exclusive reservation.
    reservation = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.replace(copy, target)
    except BaseException:
        with suppress(FileNotFoundError):
            current = target.lstat()
            if current.st_size == 0 and os.path.samestat(current, os.fstat(reservation)):
                target.unlink()
        raise
    finally:
        os.close(reservation)


def backup_stopped_journal(journal, destination, *, minimum_events=0):
    source = Path(journal).expanduser().resolve(strict=True)
    target = backup_destination(source, destination)
    with TemporaryDirectory(prefix=".alpha-paper-backup-", dir=target.parent) as temporary:
        copy = Path(temporary) / "backup.sqlite3"
        snapshot_read_only(source, copy)
        receipt = verify_pair(source, copy, minimum_events=minimum_events)
        if receipt["backup_relationship"] != "EXACT_FILL_HISTORY":
            raise ValueError("backup fill history differs from the journal: HALT")
        publish_verified_file(copy, target)
    return {"status": "PASS", "backup": str(target), "events": receipt["backup"]["events"],
            "backup_relationship": receipt["backup_relationship"]}


def _publish_copy(source_copy, original, target):
    if original["checkpoint"] == "AUTHORITY_REQUIRED":
        raise ValueError("protected journal needs its original checkpoint authority")
    if original["account"] is None:
        raise ValueError("terminal journal has no owner binding")
    config = original["profile"]
    costs = DEFAULT_COSTS if config is None else PaperCosts(
        Decimal(config["fee"]), Decimal(config["slippage"]))
    market = COINBASE_MARKET
    feed = PaperMarketFeed()
    clock_options = {}
    if config is not None and config.get("market") == ETF_FIXTURE_MARKET.name:
        market, feed = ETF_FIXTURE_MARKET, SyntheticEtfFeed()
        clock_options["clock"] = feed.clock
    copy = source_copy.rename(source_copy.parent / JOURNAL_NAME)
    paper = LivePaperSession(copy.parent, original["account"], feed, market=market, costs=costs,
                             migrate=original["schema"] == "LEGACY", **clock_options)
    try:
        if not paper.runtime.ledger.halted:
            raise ValueError("working copy failed startup HALT")
    finally:
        paper.close()
    recovered = inspect_snapshot(copy)
    for key in ("events", "head", "account", "cash_usd", "positions", "fees_usd", "realised_usd"):
        if original[key] != recovered[key]:
            raise ValueError("working copy replay changed the verified journal: HALT")
    if recovered["schema"] != "CURRENT" or recovered["stored_armed_flag"] != 0:
        raise ValueError("working copy did not recover into the current halted schema")
    target.mkdir(mode=0o700)
    try:
        publish_verified_file(copy, target / JOURNAL_NAME)
    except OSError:
        target.rmdir()
        raise
    return {"status": "PASS", "working_journal": str(target / JOURNAL_NAME), **recovered}


def prepare_working_copy(journal, backup, destination, *, minimum_events=0):
    target = Path(destination).expanduser().resolve()
    if target.exists():
        raise FileExistsError("working directory already exists")
    with TemporaryDirectory(prefix=".alpha-paper-prepare-", dir=target.parent) as temporary:
        result, source_copy = _verify_pair(journal, backup, Path(temporary), minimum_events=minimum_events)
        return _publish_copy(source_copy, result["journal"], target)


def restore_backup(backup, destination, *, expected_sequence, expected_head):
    target = Path(destination).expanduser().resolve()
    if target.exists():
        raise FileExistsError("working directory already exists")
    with TemporaryDirectory(prefix=".alpha-paper-restore-", dir=target.parent) as temporary:
        snapshot = Path(temporary) / "backup.sqlite3"
        snapshot_read_only(backup, snapshot)
        original = inspect_snapshot(snapshot)
        if (original["events"], original["head"]) != (expected_sequence, expected_head):
            raise ValueError("backup disagrees with the supplied independent checkpoint: HALT")
        return _publish_copy(snapshot, original, target)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for verb in ("verify", "prepare-copy"):
        action = commands.add_parser(verb)
        action.add_argument("--journal", required=True)
        action.add_argument("--backup", required=True)
        action.add_argument("--minimum-events", type=int, default=0)
        if verb == "verify":
            action.add_argument("--expected-sequence", type=int)
            action.add_argument("--expected-head")
        else:
            action.add_argument("--destination", required=True)
    restore = commands.add_parser("restore-backup")
    restore.add_argument("--backup", required=True)
    restore.add_argument("--destination", required=True)
    restore.add_argument("--expected-sequence", type=int, required=True)
    restore.add_argument("--expected-head", required=True)
    backup = commands.add_parser("backup", help="verify a stopped journal and save a new backup")
    backup.add_argument("--journal", required=True)
    backup.add_argument("--destination", required=True)
    backup.add_argument("--minimum-events", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        if getattr(args, "minimum_events", 0) < 0:
            raise ValueError("minimum event count must be nonnegative")
        if args.command == "verify":
            result = verify_pair(args.journal, args.backup, minimum_events=args.minimum_events,
                                 expected_sequence=args.expected_sequence, expected_head=args.expected_head)
        elif args.command == "prepare-copy":
            result = prepare_working_copy(args.journal, args.backup, args.destination,
                                          minimum_events=args.minimum_events)
        elif args.command == "backup":
            result = backup_stopped_journal(args.journal, args.destination, minimum_events=args.minimum_events)
        else:
            result = restore_backup(args.backup, args.destination, expected_sequence=args.expected_sequence,
                                    expected_head=args.expected_head)
    except (OSError, ValueError, TypeError, KeyError, DecimalException, sqlite3.Error) as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
