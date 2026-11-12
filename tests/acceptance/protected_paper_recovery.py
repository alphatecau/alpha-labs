"""Rehearse backup, restore and interrupted writes on a new loopback-only PostgreSQL cluster."""
import argparse
import json
import os
import shutil
import socket
import sqlite3
import subprocess
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

import psycopg

from alpha_lab.research.live_paper_session import LivePaperSession, PaperRejection
from deployment.postgres_paper_checkpoints import PostgresPaperCheckpoints, checkpoint_schema
from test_paper_commit_boundaries import FixedFeed, NOW, ORDER

OWNER = "oidc_" + "c" * 64
KEY = b"disposable-recovery-fixture-key!"
ADMIN = "alpha_fixture_operator"
PASSWORD = "disposable-recovery-only"
CHECKPOINT_ROLE = "alpha_fixture_checkpoint"
SOURCE_DB = "fixture_source"


class DisposablePostgres:
    def __init__(self, binaries, directory):
        self.binaries = binaries
        self.directory = directory
        self.data = directory / "pgdata"
        with socket.socket() as port:
            port.bind(("127.0.0.1", 0))
            self.port = port.getsockname()[1]
        password_file = directory / "test-password"
        password_file.write_text(PASSWORD + "\n", encoding="ascii")
        password_file.chmod(0o600)
        self.run("initdb", "-D", self.data, f"--username={ADMIN}", f"--pwfile={password_file}",
                 "--auth-host=scram-sha-256", "--auth-local=scram-sha-256")
        password_file.unlink()
        self.running = False

    def run(self, program, *args):
        result = subprocess.run([str(self.binaries / program), *map(str, args)],
                                env={**os.environ, "PGPASSWORD": PASSWORD}, timeout=30,
                                capture_output=True, text=True, check=False)
        if result.returncode:
            raise RuntimeError(f"disposable {program} failed: {result.stderr.strip()}")

    def start(self):
        self.run("pg_ctl", "-D", self.data, "-l", self.directory / "postgres.log",
                 "-o", f"-h 127.0.0.1 -p {self.port} -c unix_socket_directories=", "-w", "start")
        self.running = True

    def stop(self):
        if self.running:
            self.run("pg_ctl", "-D", self.data, "-m", "fast", "-w", "stop")
            self.running = False

    def connect(self, database, *, user=ADMIN, autocommit=False):
        return psycopg.connect(host="127.0.0.1", port=self.port, dbname=database, user=user,
                               password=PASSWORD, connect_timeout=2, autocommit=autocommit)

    def setup(self):
        with self.connect("postgres", autocommit=True) as admin:
            admin.execute("CREATE DATABASE fixture_source")
            admin.execute("CREATE DATABASE fixture_stale")
            admin.execute("CREATE DATABASE fixture_verified")
            admin.execute("CREATE ROLE alpha_fixture_checkpoint LOGIN NOINHERIT PASSWORD 'disposable-recovery-only'")
        with self.connect(SOURCE_DB) as admin:
            admin.execute(checkpoint_schema(OWNER))
            admin.execute("GRANT SELECT,INSERT ON public.paper_journal_checkpoints TO alpha_fixture_checkpoint")

    def store(self, database=SOURCE_DB, *, owner=OWNER):
        return PostgresPaperCheckpoints(lambda: self.connect(database, user=CHECKPOINT_ROLE),
                                        owner_id=owner, verification_key=KEY)

    def dump(self, path):
        self.run("pg_dump", "-h", "127.0.0.1", "-p", self.port, "-U", ADMIN,
                 "-d", SOURCE_DB, "--format=custom", "--table=public.paper_journal_checkpoints", "-f", path)

    def restore(self, path, database):
        self.run("pg_restore", "-h", "127.0.0.1", "-p", self.port, "-U", ADMIN, "-d", database,
                 "--exit-on-error", "--single-transaction", path)


def open_paper(directory, store, *, provision=False):
    return LivePaperSession(directory, OWNER, FixedFeed(), clock=lambda: NOW,
                            checkpoint_store=store, provision=provision)


def backup(paper, path):
    with closing(sqlite3.connect(path)) as destination:
        paper.db.backup(destination)
        assert destination.execute("PRAGMA quick_check").fetchone() == ("ok",)


def check_refusal(directory, store):
    try:
        paper = open_paper(directory, store)
    except ValueError as exc:
        assert "checkpoint mismatch" in str(exc)
        return
    paper.close()
    raise AssertionError("mismatched restore was accepted")


def rehearse(pg, root):
    pg.setup()
    source, restored = root / "source", root / "verified-restore"
    source.mkdir()
    restored.mkdir()
    paper = open_paper(source, pg.store(), provision=True)
    try:
        paper.control("arm", expected_revision=paper.state()["risk"]["revision"])
        assert paper.order(ORDER)["status"] == "SIMULATED_FILL"
        old = root / "stale.dump"
        pg.dump(old)
        paper.control("halt")
        checkpoint = paper.state()["recovery"]["checkpoint_sequence"]
        fresh = root / "current.dump"
        pg.dump(fresh)
        backup(paper, restored / "alpha-paper.sqlite3")
        pg.restore(old, "fixture_stale")
        check_refusal(restored, pg.store("fixture_stale"))
        pg.restore(fresh, "fixture_verified")
        verified = open_paper(restored, pg.store("fixture_verified"))
        try:
            assert verified.state()["recovery"]["checkpoint_sequence"] == checkpoint
            assert verified.state()["risk"]["reason"] == "OPERATOR_HALT"
            assert verified.order(ORDER)["status"] == "ALREADY_COMMITTED"
            assert verified.runtime.ledger.sequence == 1
        finally:
            verified.close()

        paper.control("arm", expected_revision=paper.state()["risk"]["revision"])
        original_append = paper.runtime.journal.append

        def cut_authority(*args, **kwargs):
            head = original_append(*args, **kwargs)
            pg.stop()
            return head

        paper.runtime.journal.append = cut_authority
        try:
            paper.order({**ORDER, "order_id": "interrupted_recovery_fixture_02"})
        except PaperRejection as exc:
            assert (exc.code, exc.status) == ("CHECKPOINT_HALT", 503)
        else:
            raise AssertionError("operation acknowledged without its authority")
        assert paper.runtime.ledger.halted
    finally:
        paper.close()

    pg.start()
    check_refusal(source, pg.store())
    return {"stale_restore_refused": True, "matching_restore_halted": True, "idempotent_fills": 1,
            "postgres_stopped_during_write": True, "uncertain_restart_refused": True,
            "checkpoint_sequence": checkpoint}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres-bin", type=Path, required=True)
    args = parser.parse_args()
    if not shutil.which(str(args.postgres_bin / "pg_ctl")):
        parser.error("PostgreSQL binaries are required")
    with TemporaryDirectory(prefix="alpha-recovery-") as directory:
        root = Path(directory)
        pg = DisposablePostgres(args.postgres_bin.resolve(), root)
        try:
            pg.start()
            print(json.dumps(rehearse(pg, root), sort_keys=True))
        finally:
            pg.stop()


if __name__ == "__main__":
    main()
