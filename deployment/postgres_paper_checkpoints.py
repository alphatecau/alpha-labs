"""Single-owner append-only checkpoint authority, separate from the paper disk.

An operator installs the schema and grants a dedicated LOGIN NOINHERIT role only
SELECT/INSERT. The independent signing key is injected, never stored in either
database. No migration, credential lookup, default connection or listener runs
here. Loss/rollback of both authorities still needs independent backup policy.
"""
import hmac
import re

from alpha_lab.research.paper_checkpoint import seal_state_checkpoint


def checkpoint_schema(owner_id):
    """Return isolated single-owner DDL for an authorized migration operator."""
    if not isinstance(owner_id, str) or not re.fullmatch(r"oidc_[a-f0-9]{64}", owner_id):
        raise ValueError("pinned internal checkpoint owner required")
    # Only validated lowercase hex is interpolated; SQL identifiers are fixed.
    return f"""CREATE TABLE public.paper_journal_checkpoints (
        sequence bigint PRIMARY KEY CHECK (sequence >= 0),
        owner_id text NOT NULL,
        head text NOT NULL CHECK (head ~ '^[a-f0-9]{{64}}$'),
        envelope text NOT NULL,
        CONSTRAINT checkpoint_owner_binding CHECK (owner_id = '{owner_id}')
    )"""


class PostgresPaperCheckpoints:
    def __init__(self, connect, *, owner_id, verification_key):
        checkpoint_schema(owner_id)
        if not callable(connect) or not isinstance(verification_key, bytes) or len(verification_key) < 32:
            raise ValueError("separate checkpoint connection and independent key required")
        self.connect, self.owner_id = connect, owner_id
        self._verification_key = verification_key

    @property
    def verification_key(self):
        return self._verification_key

    def _check(self, conn):
        if conn.autocommit:
            raise PermissionError("transactional checkpoint connection required")
        conn.execute("SET LOCAL search_path = pg_catalog")
        conn.execute("SET LOCAL lock_timeout = '2s'")
        conn.execute("SET LOCAL statement_timeout = '4s'")
        row = conn.execute("""
            SELECT current_user, session_user, r.rolsuper, r.rolbypassrls,
                   r.rolcreaterole, r.rolcreatedb, r.rolreplication, r.rolinherit,
                   EXISTS (SELECT 1 FROM pg_auth_members WHERE member=r.oid),
                   has_schema_privilege(current_user, 'public', 'CREATE'),
                   c.relowner=r.oid, pg_get_constraintdef(k.oid), k.convalidated,
                   has_table_privilege(current_user, c.oid, 'SELECT'),
                   has_table_privilege(current_user, c.oid, 'INSERT'),
                   has_table_privilege(current_user, c.oid, 'UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES'),
                   has_any_column_privilege(current_user, c.oid, 'UPDATE,REFERENCES'),
                   has_table_privilege(current_user, c.oid, 'SELECT WITH GRANT OPTION,INSERT WITH GRANT OPTION')
            FROM pg_roles r JOIN pg_class c ON c.relname='paper_journal_checkpoints'
            JOIN pg_namespace n ON n.oid=c.relnamespace AND n.nspname='public'
            JOIN pg_constraint k ON k.conrelid=c.oid AND k.conname='checkpoint_owner_binding'
            WHERE r.rolname=current_user AND r.rolcanlogin AND c.relkind='r' AND c.relpersistence='p'
        """).fetchone()
        expected = "CHECKowner_id='" + self.owner_id + "'::text"
        if (row is None or row[0] != row[1] or any(row[2:11])
                or re.sub(r"[()\s]", "", row[11]) != expected or row[12] is not True
                or row[13:] != (True, True, False, False, False)):
            raise PermissionError("least-privilege single-owner checkpoint authority required")

    def _latest(self, conn):
        row = conn.execute("SELECT sequence,head,envelope FROM public.paper_journal_checkpoints "
                           "WHERE owner_id=%s ORDER BY sequence DESC LIMIT 1", (self.owner_id,)).fetchone()
        if row is not None:
            self._authenticate(row)
        return row

    def _authenticate(self, row):
        expected = seal_state_checkpoint(owner=self.owner_id, sequence=row[0], head=row[1],
                                         secret=self._verification_key)
        if not isinstance(row[2], str) or not hmac.compare_digest(row[2], expected):
            raise PermissionError("checkpoint authentication failed")

    def history(self):
        with self.connect() as conn:
            self._check(conn)
            rows = conn.execute("SELECT sequence,head,envelope FROM public.paper_journal_checkpoints "
                                "WHERE owner_id=%s ORDER BY sequence DESC LIMIT 15", (self.owner_id,)).fetchall()
            if not rows:
                raise ValueError("protected checkpoints missing")
            for offset, row in enumerate(rows):
                self._authenticate(row)
                if row[0] != rows[0][0] - offset:
                    raise ValueError("protected checkpoint history has a gap")
        return [{"sequence": row[0], "head": row[1]} for row in rows]

    def load(self):
        with self.connect() as conn:
            self._check(conn)
            row = self._latest(conn)
            return row[2] if row else None

    def ready(self):
        return self.load() is not None

    def record(self, *, sequence, head, expected_sequence, expected_head):
        envelope = seal_state_checkpoint(owner=self.owner_id, sequence=sequence, head=head,
                                         secret=self._verification_key)
        with self.connect() as conn:
            self._check(conn)
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (self.owner_id,))
            previous = self._latest(conn)
            observed = previous[:2] if previous else (None, None)
            if observed != (expected_sequence, expected_head):
                raise PermissionError("checkpoint authority changed: HALT")
            if sequence != (previous[0] + 1 if previous else 0):
                raise PermissionError("checkpoint sequence must advance by one: HALT")
            conn.execute("INSERT INTO public.paper_journal_checkpoints(sequence,owner_id,head,envelope) "
                         "VALUES(%s,%s,%s,%s)", (sequence, self.owner_id, head, envelope))
        return envelope
