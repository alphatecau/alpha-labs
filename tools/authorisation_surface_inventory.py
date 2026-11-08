"""Conservative static inventory of research authorisation surfaces.

This is a discovery aid, not proof of exhaustive runtime call-graph coverage.
It never imports application modules or executes inspected source files.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

KEYWORDS = (
    "promotion_authorised", "live_trading_authorised",
    "eligible_for_strategy_promotion", "decide_strategy_promotion",
    "evaluate_archived_research_evidence", "run_assessment",
)
SCAN_DIRS = ("packages", "tools", "apps", "scripts")


def inventory(root: Path) -> dict:
    findings = []
    errors = []
    for dirname in SCAN_DIRS:
        base = root / dirname
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            relative = path.relative_to(root).as_posix()
            try:
                source = path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=relative)
            except (OSError, UnicodeError, SyntaxError) as exc:
                errors.append({"path": relative, "error": type(exc).__name__})
                continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                segment = ast.get_source_segment(source, node) or ""
                matched = sorted(key for key in KEYWORDS if key in segment)
                if matched:
                    findings.append({
                        "path": relative, "function": node.name,
                        "line": node.lineno, "keywords": matched,
                    })
    js_findings = []
    js_patterns = (
        "promotion_authorised", "live_trading_authorised",
        "trading_enabled", "fetch(", "addEventListener(", "/api/v",
    )
    for dirname in SCAN_DIRS:
        base = root / dirname
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.js")):
            relative = path.relative_to(root).as_posix()
            try:
                source = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                errors.append({"path": relative, "error": type(exc).__name__})
                continue
            for lineno, line in enumerate(source.splitlines(), 1):
                matched = [pattern for pattern in js_patterns if pattern in line]
                if matched:
                    js_findings.append({"path": relative, "line": lineno, "patterns": matched})
    return {
        "javascript_surface_findings": js_findings,
        "javascript_ast_verified": False,
        "schema": "alpha-labs.static-authorisation-inventory.v1",
        "runtime_call_graph_verified": False,
        "entry_points_exhaustively_verified": False,
        "promotion_authorised": False,
        "live_trading_authorised": False,
        "findings": findings,
        "parse_errors": errors,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    result = inventory(args.root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["parse_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
