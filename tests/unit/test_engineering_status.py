"""Offline regression and adversarial tests for read-only CI evidence collection."""
import contextlib
import http.client
import importlib.util
import io
import json
import os
import pathlib
import tempfile
import unittest
import urllib.error
from unittest import mock
from urllib.parse import parse_qs, urlsplit

PATH = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "engineering_status.py"
SPEC = importlib.util.spec_from_file_location("engineering_status", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

MAIN, OLD, OTHER = "a" * 40, "b" * 40, "c" * 40


def pr(number=76, sha=OLD):
    return {"number": number, "title": "Research", "draft": True,
            "html_url": f"https://github.com/alphatecau/alpha-labs/pull/{number}",
            "head": {"sha": sha}}


def run(number=1, sha=OLD, *, event="pull_request", status="completed", conclusion="success"):
    return {"id": number, "head_sha": sha, "name": "unit", "event": event,
            "status": status, "conclusion": conclusion,
            "html_url": f"https://github.com/alphatecau/alpha-labs/actions/runs/{number}"}


class Transport:
    def __init__(self, *, prs=None, runs=None):
        self.prs = {1: [pr()]} if prs is None else prs
        self.runs = runs or {}
        self.calls = []

    def __call__(self, path):
        self.calls.append(path)
        parsed = urlsplit(path)
        query = parse_qs(parsed.query)
        if parsed.path == "/branches/main":
            return {"commit": {"sha": MAIN}}
        page = int(query["page"][0])
        if parsed.path == "/pulls":
            value = self.prs.get(page, [])
        elif parsed.path == "/actions/runs":
            # The global recent-run window must never be queried.
            sha = query["head_sha"][0]
            value = self.runs.get((sha, page), {"total_count": 0, "workflow_runs": []})
        else:
            raise AssertionError("unexpected API path")
        if isinstance(value, Exception):
            raise value
        return value


class EngineeringStatusTests(unittest.TestCase):
    def test_correlates_checks_by_exact_commit(self):
        result = MODULE.summarise([pr()], {"workflow_runs": [
            run(), run(2, OTHER, conclusion="failure")]})
        checks = result["open_prs"][0]["recent_checks"]
        self.assertEqual([r["id"] for r in checks], [1])

    def test_missing_checks_are_not_inferred_as_passed(self):
        result = MODULE.collect(fetch=Transport())
        item = result["open_prs"][0]
        self.assertEqual(item["recent_checks"], [])
        self.assertEqual(item["collection_state"], "missing")
        self.assertIn("not proof of passing", result["note"])
        self.assertEqual(result["collection"]["state"], "complete")

    def test_collects_older_failed_heads_and_main(self):
        transport = Transport(prs={1: [pr(42), pr(76, OTHER)]}, runs={
            (MAIN, 1): {"total_count": 1, "workflow_runs": [run(10, MAIN)]},
            (OLD, 1): {"total_count": 1, "workflow_runs": [run(20, conclusion="failure")]},
            (OTHER, 1): {"total_count": 1, "workflow_runs": [run(30, OTHER, conclusion="failure")]},
        })
        result = MODULE.collect(fetch=transport)
        self.assertEqual(result["main"]["head_sha"], MAIN)
        self.assertEqual(result["main"]["recent_checks"][0]["id"], 10)
        self.assertEqual([p["recent_checks"][0]["conclusion"] for p in result["open_prs"]],
                         ["failure", "failure"])
        self.assertEqual(result["collection"]["state"], "complete")

    def test_paginates_more_than_100_prs_and_runs_deduplicating_heads(self):
        transport = Transport(prs={1: [pr(n) for n in range(1, 101)], 2: [pr(101)]},
                              runs={
                                  (OLD, 1): {"total_count": 101, "workflow_runs": [run(n) for n in range(1, 101)]},
                                  (OLD, 2): {"total_count": 101, "workflow_runs": [run(101)]},
                              })
        result = MODULE.collect(fetch=transport)
        self.assertEqual(result["collection"]["state"], "complete")
        self.assertEqual(len(result["open_prs"]), 101)
        self.assertEqual(len(result["open_prs"][0]["recent_checks"]), 101)
        self.assertEqual(sum("/actions/runs?" in p for p in transport.calls), 3)

    def test_deduplicates_overlapping_run_pages(self):
        transport = Transport(runs={
            (OLD, 1): {"total_count": 3, "workflow_runs": [run(1), run(2)]},
            (OLD, 2): {"total_count": 3, "workflow_runs": [run(2), run(3)]},
        })
        with mock.patch.object(MODULE, "PAGE_SIZE", 2):
            result = MODULE.collect(fetch=transport)
        self.assertEqual(result["collection"]["state"], "complete")
        self.assertEqual([r["id"] for r in result["open_prs"][0]["recent_checks"]], [3, 2, 1])

    def test_shared_main_and_pr_sha_is_fetched_once(self):
        transport = Transport(prs={1: [pr(1, MAIN), pr(2, MAIN)]})
        result = MODULE.collect(fetch=transport)
        self.assertEqual(result["collection"]["state"], "complete")
        self.assertEqual(sum("/actions/runs?" in p for p in transport.calls), 1)

    def test_manual_and_scheduled_runs_do_not_verify_tested_checkout(self):
        transport = Transport(runs={(OLD, 1): {"total_count": 2, "workflow_runs": [
            run(1, event="workflow_dispatch"), run(2, event="schedule")]}})
        result = MODULE.collect(fetch=transport)
        item = result["open_prs"][0]
        self.assertEqual(item["recent_checks"], [])
        self.assertEqual(item["collection_state"], "missing")
        self.assertEqual([r["target_verified"] for r in item["other_runs"]], [False, False])

    def test_push_only_evidence_and_non_success_states_are_preserved(self):
        transport = Transport(runs={(OLD, 1): {"total_count": 3, "workflow_runs": [
            run(1, event="push", conclusion="failure"),
            run(2, status="queued", conclusion=None),
            run(3, conclusion="cancelled")]}})
        result = MODULE.collect(fetch=transport)
        item = result["open_prs"][0]
        self.assertEqual(item["collection_state"], "complete")
        self.assertEqual([r["conclusion"] for r in item["recent_checks"]],
                         ["cancelled", None, "failure"])
        self.assertNotIn("passed", item)

    def test_mismatched_sha_is_incomplete_and_not_attributed(self):
        result = MODULE.collect(fetch=Transport(runs={
            (OLD, 1): {"total_count": 1, "workflow_runs": [run(1, OTHER)]}}))
        self.assertEqual(result["collection"]["state"], "incomplete")
        self.assertEqual(result["open_prs"][0]["recent_checks"], [])
        self.assertEqual(result["open_prs"][0]["collection_state"], "incomplete")

    def test_pagination_limit_preserves_partial_runs_and_uninspected_heads(self):
        transport = Transport(prs={1: [pr(42), pr(76, OTHER)]}, runs={
            (OLD, 1): {"total_count": 1001, "workflow_runs": [run(n) for n in range(1, 101)]}})
        with mock.patch.object(MODULE, "MAX_RUN_PAGES", 1):
            result = MODULE.collect(fetch=transport)
        self.assertEqual(result["collection"]["state"], "incomplete")
        self.assertEqual(len(result["open_prs"][0]["recent_checks"]), 100)
        self.assertTrue(all(p["collection_state"] == "incomplete" for p in result["open_prs"]))
        self.assertIn("pagination limit", result["collection"]["errors"][0]["reason"])

    def test_truncated_run_page_is_incomplete(self):
        result = MODULE.collect(fetch=Transport(runs={
            (OLD, 1): {"total_count": 2, "workflow_runs": [run()]}}))
        self.assertEqual(result["collection"]["state"], "incomplete")
        self.assertEqual(len(result["open_prs"][0]["recent_checks"]), 1)

    def test_invalid_run_responses_are_incomplete(self):
        for data in ([], {}, {"total_count": True, "workflow_runs": []},
                     {"total_count": -1, "workflow_runs": []},
                     {"total_count": 1, "workflow_runs": [None]},
                     {"total_count": 1, "workflow_runs": [{"id": 1}]},
                     {"total_count": 1, "workflow_runs": [run(number=True)]}):
            with self.subTest(data=data):
                result = MODULE.collect(fetch=Transport(runs={(OLD, 1): data}))
                self.assertEqual(result["collection"]["state"], "incomplete")

    def test_failure_on_pr_page_two_preserves_inventory_but_marks_it_incomplete(self):
        transport = Transport(prs={1: [pr(n) for n in range(1, 101)],
                                   2: urllib.error.URLError("sensitive upstream message")})
        result = MODULE.collect(fetch=transport)
        self.assertEqual(len(result["open_prs"]), 100)
        self.assertFalse(result["collection"]["pull_requests_complete"])
        self.assertEqual(result["collection"]["state"], "incomplete")
        self.assertNotIn("sensitive", json.dumps(result))

    def test_invalid_or_repeated_pr_is_incomplete(self):
        for pages in ({1: [None]}, {1: [pr(0)]}, {1: [pr(sha="invalid")]},
                      {1: [pr(), pr()]}):
            with self.subTest(pages=pages):
                result = MODULE.collect(fetch=Transport(prs=pages))
                self.assertEqual(result["collection"]["state"], "incomplete")
                self.assertFalse(result["collection"]["pull_requests_complete"])

    def test_pr_pagination_limit_is_explicit(self):
        transport = Transport(prs={1: [pr()]})
        with mock.patch.object(MODULE, "PAGE_SIZE", 1), mock.patch.object(MODULE, "MAX_PR_PAGES", 1):
            result = MODULE.collect(fetch=transport)
        self.assertEqual(len(result["open_prs"]), 1)
        self.assertFalse(result["collection"]["pull_requests_complete"])
        self.assertIn("pagination limit", result["collection"]["errors"][0]["reason"])

    def test_invalid_main_response_is_incomplete(self):
        for response in (None, {}, {"commit": {"sha": "wrong"}}):
            with self.subTest(response=response):
                result = MODULE.collect(fetch=lambda _: response)
                self.assertIsNone(result["main"]["head_sha"])
                self.assertEqual(result["collection"]["state"], "incomplete")

    def test_budget_exhaustion_stops_before_next_request(self):
        transport = Transport()
        ticks = iter([0, 0, 0, 480])
        result = MODULE.collect(fetch=transport, clock=lambda: next(ticks))
        self.assertEqual(transport.calls, ["/branches/main"])
        self.assertEqual(result["main"]["head_sha"], MAIN)
        self.assertEqual(result["collection"]["state"], "incomplete")
        self.assertIn("time budget", result["collection"]["errors"][0]["reason"])

    def test_budget_exhaustion_after_slow_request_is_incomplete(self):
        ticks = iter([0, 0, 481])
        result = MODULE.collect(fetch=Transport(), clock=lambda: next(ticks))
        self.assertEqual(result["collection"]["state"], "incomplete")

    def test_fetch_uses_fixed_get_origin_and_optional_token_without_mutating_headers(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{"ok":true}'
        opener = mock.Mock()
        opener.open.return_value = response
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "synthetic-test-token"}, clear=True), \
                mock.patch.object(MODULE.urllib.request, "build_opener", return_value=opener) as build:
            self.assertEqual(MODULE.fetch_json("/branches/main"), {"ok": True})
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, MODULE.API + "/branches/main")
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("Authorization"), "Bearer synthetic-test-token")
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 15)
        self.assertIsInstance(build.call_args.args[0], MODULE.RejectRedirects)
        self.assertNotIn("Authorization", MODULE.HEADERS)

    def test_fetch_without_token_stays_anonymous(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b"{}"
        opener = mock.Mock()
        opener.open.return_value = response
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(MODULE.urllib.request, "build_opener", return_value=opener):
            MODULE.fetch_json("/branches/main")
        self.assertIsNone(opener.open.call_args.args[0].get_header("Authorization"))

    def test_fetch_rejects_non_repository_paths_without_network(self):
        with mock.patch.object(MODULE.urllib.request, "build_opener") as build:
            for path in ("https://other.example", "//other.example", "/path#fragment", None):
                with self.subTest(path=path), self.assertRaises(MODULE.CollectionError):
                    MODULE.fetch_json(path)
            build.assert_not_called()

    def test_redirect_is_rejected_before_another_request(self):
        with self.assertRaisesRegex(MODULE.CollectionError, "redirect refused"):
            MODULE.RejectRedirects().redirect_request(None, None, 302, "", {}, "https://other.example")

    def test_http_denials_and_timeouts_are_sanitized(self):
        for error, diagnostic in (
            (urllib.error.HTTPError("https://example/?sensitive", 403, "sensitive", {}, None), "HTTP 403"),
            (urllib.error.HTTPError("https://example/?sensitive", 429, "sensitive", {}, None), "HTTP 429"),
            (TimeoutError("sensitive"), "request or JSON"),
        ):
            with self.subTest(error=type(error).__name__):
                opener = mock.Mock()
                opener.open.side_effect = error
                with mock.patch.object(MODULE.urllib.request, "build_opener", return_value=opener):
                    with self.assertRaises(MODULE.CollectionError) as caught:
                        MODULE.fetch_json("/branches/main")
                self.assertIn(diagnostic, str(caught.exception))
                self.assertNotIn("sensitive", str(caught.exception))

    def test_invalid_json_and_oversized_response_are_sanitized(self):
        for raw in (b"sensitive invalid JSON", b"x" * (MODULE.MAX_RESPONSE_BYTES + 1)):
            with self.subTest(oversized=len(raw) > MODULE.MAX_RESPONSE_BYTES):
                response = mock.MagicMock()
                response.__enter__.return_value = response
                response.read.return_value = raw
                opener = mock.Mock()
                opener.open.return_value = response
                with mock.patch.object(MODULE.urllib.request, "build_opener", return_value=opener):
                    with self.assertRaises(MODULE.CollectionError) as caught:
                        MODULE.fetch_json("/branches/main")
                self.assertNotIn("sensitive", str(caught.exception))

    def test_cli_writes_partial_report_and_exits_nonzero_without_secret_diagnostics(self):
        with tempfile.TemporaryDirectory() as folder:
            output = pathlib.Path(folder) / "report.json"
            with mock.patch.object(MODULE, "fetch_json", side_effect=TimeoutError("sensitive")), \
                    mock.patch.object(MODULE.sys, "argv", ["engineering_status.py", "--output", str(output)]), \
                    contextlib.redirect_stdout(io.StringIO()) as stdout, \
                    contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(MODULE.main(), 1)
            report = output.read_text()
            self.assertEqual(json.loads(report)["collection"]["state"], "incomplete")
            self.assertNotIn("sensitive", report + stdout.getvalue() + stderr.getvalue())

    def test_cli_success_means_collection_only_even_when_ci_fails(self):
        transport = Transport(runs={(OLD, 1): {"total_count": 1, "workflow_runs": [
            run(conclusion="failure")]}})
        with tempfile.TemporaryDirectory() as folder:
            output = pathlib.Path(folder) / "report.json"
            with mock.patch.object(MODULE, "fetch_json", side_effect=transport), \
                    mock.patch.object(MODULE.sys, "argv", ["engineering_status.py", "--output", str(output)]), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(MODULE.main(), 0)
            report = json.loads(output.read_text())
            self.assertEqual(report["open_prs"][0]["recent_checks"][0]["conclusion"], "failure")

    def test_inconsistent_total_count_cannot_be_complete(self):
        result = MODULE.collect(fetch=Transport(runs={
            (OLD, 1): {"total_count": 0, "workflow_runs": [run()]}}))
        self.assertEqual(result["collection"]["state"], "incomplete")
        self.assertEqual(result["open_prs"][0]["recent_checks"], [])

    def test_completed_missing_or_invalid_conclusions_are_incomplete(self):
        for overrides in ({"conclusion": None}, {"status": "PASS"},
                          {"conclusion": "PASS"}, {"status": "queued", "conclusion": "success"}):
            with self.subTest(overrides=overrides):
                item = run()
                item.update(overrides)
                result = MODULE.collect(fetch=Transport(runs={
                    (OLD, 1): {"total_count": 1, "workflow_runs": [item]}}))
                self.assertEqual(result["collection"]["state"], "incomplete")
        item = run()
        del item["conclusion"]
        result = MODULE.collect(fetch=Transport(runs={
            (OLD, 1): {"total_count": 1, "workflow_runs": [item]}}))
        self.assertEqual(result["collection"]["state"], "incomplete")

    def test_truncated_http_preserves_partial_report_and_exits_nonzero(self):
        transport = Transport(runs={
            (MAIN, 1): {"total_count": 1, "workflow_runs": [run(10, MAIN)]},
            (OLD, 1): http.client.IncompleteRead(b"sensitive", 100),
        })
        with tempfile.TemporaryDirectory() as folder:
            output = pathlib.Path(folder) / "report.json"
            with mock.patch.object(MODULE, "fetch_json", side_effect=transport), \
                    mock.patch.object(MODULE.sys, "argv", ["audit", "--output", str(output)]), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(MODULE.main(), 1)
            report = json.loads(output.read_text())
            self.assertEqual(report["main"]["recent_checks"][0]["id"], 10)
            self.assertEqual(report["open_prs"][0]["collection_state"], "incomplete")
            self.assertNotIn("sensitive", output.read_text())

    def test_response_read_http_errors_are_sanitized(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.side_effect = http.client.IncompleteRead(b"sensitive", 100)
        opener = mock.Mock()
        opener.open.return_value = response
        with mock.patch.object(MODULE.urllib.request, "build_opener", return_value=opener):
            with self.assertRaises(MODULE.CollectionError) as caught:
                MODULE.fetch_json("/branches/main")
        self.assertNotIn("sensitive", str(caught.exception))

    def test_ref_changes_are_incomplete_with_original_evidence_preserved(self):
        for latest_prs, latest_main in (([pr(sha=OTHER)], MAIN), ([], MAIN),
                                        ([pr(), pr(2, OTHER)], MAIN), ([pr()], OTHER)):
            with self.subTest(latest_prs=latest_prs, latest_main=latest_main):
                transport = Transport(runs={
                    (OLD, 1): {"total_count": 1, "workflow_runs": [run(conclusion="failure")]}})
                counts = {"main": 0, "prs": 0}
                def moving(path):
                    if path == "/branches/main":
                        counts["main"] += 1
                        if counts["main"] > 1:
                            return {"commit": {"sha": latest_main}}
                    if path.startswith("/pulls?"):
                        counts["prs"] += 1
                        if counts["prs"] > 1:
                            return latest_prs
                    return transport(path)
                result = MODULE.collect(fetch=moving)
                self.assertEqual(result["collection"]["state"], "incomplete")
                self.assertFalse(result["collection"]["pull_requests_complete"])
                self.assertEqual(result["open_prs"][0]["collection_state"], "incomplete")
                self.assertEqual(result["open_prs"][0]["recent_checks"][0]["conclusion"], "failure")

    def test_revalidation_timeout_does_not_certify_stale_heads(self):
        transport = Transport()
        calls = 0
        def failure(path):
            nonlocal calls
            if path == "/branches/main":
                calls += 1
                if calls > 1:
                    raise TimeoutError("sensitive")
            return transport(path)
        result = MODULE.collect(fetch=failure)
        self.assertEqual(result["collection"]["state"], "incomplete")
        self.assertEqual(result["open_prs"][0]["collection_state"], "incomplete")
        self.assertNotIn("sensitive", json.dumps(result))

    def test_output_failure_is_sanitized_and_nonzero(self):
        report = MODULE.collect(fetch=Transport(prs={1: []}))
        with mock.patch.object(MODULE, "collect", return_value=report), \
                mock.patch.object(MODULE.sys, "argv", ["engineering_status.py"]), \
                mock.patch("builtins.open", side_effect=OSError("sensitive")), \
                contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(MODULE.main(), 1)
        self.assertNotIn("sensitive", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
