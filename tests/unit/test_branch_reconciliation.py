"""Squash incorporation must not hide newer branch changes or missing CI."""
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("reconciliation", Path(__file__).resolve().parents[2] / "scripts/reconcile_repository.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BranchReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.repo = Path(self.directory.name)
        self.run_git("init", "-b", "main")
        self.run_git("config", "user.name", "Synthetic Audit")
        self.run_git("config", "user.email", "synthetic@example.invalid")
        self.commit("base")
        self.run_git("checkout", "-b", "feature")
        self.old_head = self.commit("feature")
        self.run_git("checkout", "main")
        self.squash = self.commit("feature", message="squashed feature")
        self.main = self.commit("later reviewed change")
        self.run_git("checkout", "feature")
        self.new_head = self.commit("new unmerged feature")

    def run_git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True, stderr=subprocess.DEVNULL).strip()

    def commit(self, text, *, message=None):
        (self.repo / "source.txt").write_text(text)
        self.run_git("add", "source.txt")
        self.run_git("commit", "-m", message or text)
        return self.run_git("rev-parse", "HEAD")

    def report(self, head, *, complete=True, run_sha=None, run_status="completed", conclusion="success", total=1):
        metadata = {"main_sha": self.main, "observed_at": "synthetic", "branches": [
            {"name": "main", "commit": {"sha": self.main}}, {"name": "feature", "commit": {"sha": head}}],
            "prs": [{"number": 97, "state": "closed", "merged_at": "synthetic", "url": "https://example.invalid/pr",
                     "head": {"ref": "feature", "sha": self.old_head}, "base": {"ref": "main", "sha": self.squash},
                     "merge_commit_sha": self.squash}]}
        run = {"id": 1, "workflow_id": 1, "event": "pull_request", "created_at": "synthetic", "status": run_status, "conclusion": conclusion, "head_sha": run_sha or head}
        ci = {"branches": [{"name": "feature", "head_sha": head, "state": "VERIFIED" if complete else "BLOCKED", "runs": [run], "total": total}]}
        return MODULE.reconcile(self.repo, metadata, ci)["branches"][1]

    def test_verified_squash_record_counts_as_integrated_after_later_main_edits(self):
        result = self.report(self.old_head)
        self.assertFalse(result["main_comparison"]["ancestor_of_main"])
        self.assertFalse(result["main_comparison"]["all_delta_files_equal_main"])
        self.assertEqual(result["disposition"], "ALREADY_INTEGRATED")

    def test_new_commit_on_previously_merged_branch_requires_new_review(self):
        result = self.report(self.new_head)
        self.assertNotEqual(result["disposition"], "ALREADY_INTEGRATED")
        self.assertEqual(result["main_comparison"]["verified_main_merge_prs"], [])

    def test_partial_or_mismatched_ci_cannot_be_ready(self):
        for kwargs in ({"complete": False}, {"run_sha": self.old_head}, {"total": 0}):
            result = self.report(self.new_head, **kwargs)
            self.assertEqual(result["ci"]["status"], "BLOCKED")
            self.assertEqual(result["disposition"], "BLOCKED")
        for kwargs in ({"run_status": "queued", "conclusion": None}, {"conclusion": "skipped"}):
            self.assertEqual(self.report(self.new_head, **kwargs)["disposition"], "BLOCKED")

    def test_git_errors_are_not_equivalence_evidence(self):
        with self.assertRaises(ValueError):
            MODULE.ancestor(self.repo, "nonexistent-ref", self.main)

    def test_manual_events_cannot_establish_tested_checkout(self):
        self.assertEqual(MODULE.latest_runs([{"created_at": "synthetic", "id": 1, "event": "workflow_dispatch"}]), [])
