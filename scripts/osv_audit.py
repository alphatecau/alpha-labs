"""Read-only OSV vulnerability check for installed Python distributions.

Uses OSV querybatch. No secrets, package changes, or deployment actions.
"""
from __future__ import annotations

import json
import sys
from importlib.metadata import distributions
from urllib.request import Request, urlopen

OSV_URL = "https://api.osv.dev/v1/querybatch"


def installed_packages():
    items = set()
    for dist in distributions():
        name = dist.metadata.get("Name")
        if name and dist.version:
            items.add((name.lower().replace("_", "-"), dist.version))
    return sorted(items)


def audit(packages, *, opener=urlopen):
    queries = [{"package": {"ecosystem": "PyPI", "name": name}, "version": version}
               for name, version in packages]
    if not queries:
        return []
    body = json.dumps({"queries": queries}).encode()
    request = Request(OSV_URL, data=body, headers={
        "Content-Type": "application/json", "User-Agent": "alpha-labs-security-audit/1"
    }, method="POST")
    with opener(request, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError("OSV service error")
        data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise RuntimeError("OSV response too large")
    result = json.loads(data)
    if not isinstance(result, dict) or not isinstance(result.get("results"), list):
        raise RuntimeError("OSV invalid response")
    if len(result["results"]) != len(queries):
        raise RuntimeError("OSV incomplete response")
    findings = []
    for (name, version), item in zip(packages, result["results"]):
        if not isinstance(item, dict):
            raise RuntimeError("OSV invalid result")
        vulns = item.get("vulns", [])
        if not isinstance(vulns, list):
            raise RuntimeError("OSV invalid vulnerabilities")
        for vuln in vulns:
            if not isinstance(vuln, dict) or not isinstance(vuln.get("id"), str):
                raise RuntimeError("OSV invalid vulnerability")
            findings.append({"package": name, "version": version, "id": vuln["id"]})
    return findings


def main():
    try:
        findings = audit(installed_packages())
        print(json.dumps({"status": "VULNERABILITIES" if findings else "PASS", "findings": findings}))
        return 1 if findings else 0
    except Exception as exc:
        print(json.dumps({"status": "UNVERIFIED", "reason": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
