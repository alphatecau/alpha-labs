"""Research-only journal: one process writer, transactional unique paper orders.

The hash chain detects ordinary corruption. A separately authenticated checkpoint
is required to detect an attacker rewriting an entire database and its hashes.
"""
import fcntl
import json
import re
import sqlite3
from hashlib import sha256

_ORDER_ID = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate journal JSON member: HALT")
        value[key] = item
    return value


class PaperJournal:
    def __init__(self, path, *, check_same_thread=True):
        if path == ":memory:":
            raise ValueError("persistent journal path required")
        self._lock_file = open(str(path) + ".writer.lock", "a+b")
        self.connection = None
        try:
            # Keep main's exclusive ownership; acquire it before migration/replay.
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._lock_file.close()
            raise PermissionError("HALT: paper journal already has a writer") from exc
        try:
            self.connection = sqlite3.connect(path, check_same_thread=check_same_thread)
            self.connection.execute("PRAGMA synchronous=FULL")
            self.connection.execute("BEGIN IMMEDIATE")
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, "
                "previous_hash TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL)"
            )
            columns = {row[1]: row for row in self.connection.execute("PRAGMA table_xinfo(events)")}
            if "order_id" not in columns:
                # Preserve original payload/hash bytes when migrating old journals.
                self.connection.execute(
                    "ALTER TABLE events ADD COLUMN order_id TEXT GENERATED ALWAYS AS "
                    "(CASE WHEN json_valid(payload) THEN json_extract(payload,'$.order_id') "
                    "ELSE NULL END) VIRTUAL"
                )
            elif columns["order_id"][6] != 2:
                raise ValueError("unexpected journal order identity schema: HALT")
            schema = self.connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='events'").fetchone()[0]
            normal_schema = re.sub(r"\s+", "", schema).lower()
            expression = "order_idtextgeneratedalwaysas(casewhenjson_valid(payload)thenjson_extract(payload,'$.order_id')elsenullend)virtual"
            if expression not in normal_schema:
                raise ValueError("unexpected generated order identity: HALT")
            self.verify()
            self.connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS events_order_id_unique "
                "ON events(order_id) WHERE order_id IS NOT NULL"
            )
            indexes = {row[1]: row for row in self.connection.execute("PRAGMA index_list(events)")}
            index = indexes.get("events_order_id_unique")
            indexed = list(self.connection.execute("PRAGMA index_info(events_order_id_unique)"))
            index_sql = self.connection.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name='events_order_id_unique'").fetchone()[0]
            normal_index = re.sub(r"\s+", "", index_sql).lower().replace("ifnotexists", "")
            if (index is None or index[2] != 1 or [row[2] for row in indexed] != ["order_id"]
                    or normal_index != "createuniqueindexevents_order_id_uniqueonevents(order_id)whereorder_idisnotnull"):
                raise ValueError("journal order uniqueness missing: HALT")
            self.connection.commit()
        except Exception:
            self.close()
            raise

    def verify(self):
        previous = "0" * 64
        expected_seq = 1
        seen_orders = set()
        for seq, prior, payload, digest in self.connection.execute(
                "SELECT seq,previous_hash,payload,digest FROM events ORDER BY seq"):
            if seq != expected_seq:
                raise ValueError("journal sequence gap: HALT")
            expected_seq += 1
            expected = sha256((previous + payload).encode()).hexdigest()
            if prior != previous or digest != expected:
                raise ValueError("journal integrity failure: HALT")
            event = json.loads(payload, object_pairs_hook=_unique_object)
            if not isinstance(event, dict):
                raise ValueError("invalid journal event: HALT")
            order_id = event.get("order_id")
            if order_id is not None:
                if not isinstance(order_id, str) or not _ORDER_ID.fullmatch(order_id):
                    raise ValueError("invalid journal order ID: HALT")
                if order_id in seen_orders:
                    raise ValueError("duplicate simulated order ID: HALT")
                seen_orders.add(order_id)
            previous = digest
        return previous

    def verify_checkpoint(self, *, trusted_sequence, trusted_head):
        """Compare with an independently authenticated and protected checkpoint."""
        if not isinstance(trusted_sequence, int) or isinstance(trusted_sequence, bool) or trusted_sequence < 0:
            raise ValueError("invalid trusted checkpoint: HALT")
        if not isinstance(trusted_head, str) or not re.fullmatch(r"[0-9a-f]{64}", trusted_head):
            raise ValueError("invalid trusted checkpoint: HALT")
        actual_head = self.verify()
        actual_sequence = self.connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        if actual_sequence != trusted_sequence or actual_head != trusted_head:
            raise ValueError("journal checkpoint mismatch: HALT")
        return actual_head

    def append(self, event, *, expected_seq=None, expected_head=None):
        if not isinstance(event, dict):
            raise ValueError("invalid journal event: HALT")
        order_id = event.get("order_id")
        if order_id is not None and (not isinstance(order_id, str) or not _ORDER_ID.fullmatch(order_id)):
            raise ValueError("invalid journal order ID: HALT")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            previous = self.verify()
            if expected_seq is not None:
                current_seq = self.connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                if current_seq != expected_seq or previous != expected_head:
                    raise ValueError("stale journal state: HALT")
            payload = json.dumps(event, sort_keys=True, separators=(",", ":"), allow_nan=False)
            digest = sha256((previous + payload).encode()).hexdigest()
            self.connection.execute(
                "INSERT INTO events(previous_hash,payload,digest) VALUES(?,?,?)",
                (previous, payload, digest)
            )
            self.connection.commit()
            return digest
        except sqlite3.IntegrityError as exc:
            self.connection.rollback()
            raise ValueError("duplicate simulated order ID or invalid journal: HALT") from exc
        except Exception:
            self.connection.rollback()
            raise

    def close(self):
        if self.connection is not None:
            self.connection.close()
        self._lock_file.close()
