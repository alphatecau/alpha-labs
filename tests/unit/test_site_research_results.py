import json
import os
import secrets
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from deployment import staging_probe as api


class SiteResearchResultsTests(unittest.TestCase):
    def setUp(self):
        self.token = secrets.token_hex(32)
        self.commit = "a" * 40
        self.enterContext(patch.dict(os.environ, ALPHA_RESEARCH_TOKEN=self.token, RENDER_GIT_COMMIT=self.commit,
                                     ALPHA_RESEARCH_TOKEN_EXPIRES_AT=str(int(time.time()) + 60)))

    def request(self, path=api.RESULTS_PATH, method="GET", query="", auth=""):
        meta = {}

        def start(status, headers):
            meta.update(status=status, headers=dict(headers))

        body = b"".join(api.application({
            "PATH_INFO": path, "REQUEST_METHOD": method, "QUERY_STRING": query, "HTTP_AUTHORIZATION": auth,
        }, start))
        return meta["status"].split()[0], meta["headers"], body

    def test_exact_repository_bytes_and_revision(self):
        status, headers, body = self.request(auth="Bearer " + self.token)
        self.assertEqual(status, "200")
        self.assertEqual(body, api.AUDIT.read_bytes())
        self.assertEqual(headers["X-Alpha-Evidence-SHA256"], api.AUDIT_SHA256)
        self.assertEqual(headers["X-Alpha-Research-Commit"], self.commit)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIs(json.loads(body)["trading_enabled"], False)

    def test_health_and_read_only_contract(self):
        self.assertEqual(json.loads(self.request("/healthz")[2])["trading"], "disabled")
        for method in ["POST", "PUT", "DELETE"]:
            self.assertEqual(self.request(method=method)[0], "405")
        for path in ["/api/v1/paper/state", "/api/v1/paper/orders", "/api/v1/live/orders"]:
            self.assertEqual(self.request(path)[0], "404")
        self.assertEqual(self.request(query="symbol=BTC")[0], "404")

    def test_configuration_and_credentials(self):
        for value in ["", "Bearer wrong", "Bearer étranger"]:
            self.assertEqual(self.request(auth=value)[0], "401")
        for name in ["RENDER_GIT_COMMIT", "ALPHA_RESEARCH_TOKEN"]:
            with patch.dict(os.environ, {name: ""}):
                self.assertEqual(self.request(auth="Bearer " + self.token)[0], "503")

    def test_expiry_is_required_and_enforced(self):
        for expiry in ("", "invalid", "0", "100", "99999999999"):
            with self.subTest(expiry=expiry), patch.dict(os.environ, ALPHA_RESEARCH_TOKEN_EXPIRES_AT=expiry):
                self.assertEqual(self.request(auth="Bearer " + self.token)[0], "503")

    def test_unavailable_or_modified_evidence(self):
        with TemporaryDirectory() as directory, patch.object(api, "AUDIT", Path(directory) / "report.json"):
            self.assertEqual(self.request(auth="Bearer " + self.token)[0], "503")
            api.AUDIT.write_text('{"trading_enabled":true}')
            self.assertEqual(self.request(auth="Bearer " + self.token)[0], "503")
