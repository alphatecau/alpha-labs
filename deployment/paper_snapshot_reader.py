"""Fail-closed tenant-scoped offline paper journal snapshot adapter.

The caller supplies an explicit owner-to-journal mapping. No HTTP write or
execution operations exist. Journals must be stopped for consistent inspection.
"""
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from alpha_lab.research.local_paper_recovery import inspect_snapshot, snapshot_read_only


class StoppedPaperSnapshotReader:
    def __init__(self, journals):
        if not isinstance(journals, dict):
            raise ValueError("explicit owner-to-journal mapping required")
        self._journals = dict(journals)

    def snapshot(self, owner):
        if not isinstance(owner, str) or not re.fullmatch(r"oidc_[a-f0-9]{64}", owner):
            raise PermissionError("unverified owner")
        source = self._journals.get(owner)
        if source is None:
            raise PermissionError("tenant paper journal not provisioned")
        with TemporaryDirectory(prefix="alpha-paper-readonly-") as temporary:
            copy = Path(temporary) / "snapshot.sqlite3"
            snapshot_read_only(source, copy)
            result = inspect_snapshot(copy)
        # The journal's owner guard is an additional binding, not a substitute
        # for the authenticated caller's tenant mapping.
        if result["account"] != owner:
            raise PermissionError("paper journal owner mismatch")
        return {"mode": "paper_only", "execution": "disabled",
                "source": "verified_stopped_sqlite_journal", **result}
