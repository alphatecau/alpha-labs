import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from alpha_lab.mirofish_transport import MiroFishLoopbackTransport
from alpha_lab.simulation_adapter import SandboxedSimulationAdapter, SimulationAdapterError
from alpha_lab.behaviour_simulation import ScenarioInput

class Handler(BaseHTTPRequestHandler):
    mode = "ok"
    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.send_response(200 if self.mode != "error" else 503)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        result = {"event_id": data["event_id"], "observations": [
            {"persona": "sceptic", "narrative": "Synthetic mock response"}]}
        if self.mode == "oversize":
            result["padding"] = "X" * 500
        self.wfile.write(json.dumps(result).encode())
    def log_message(self, *_):
        pass

class MiroFishTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
    def endpoint(self):
        return "http://127.0.0.1:%d/api/test-only" % self.server.server_port
    def test_mock_round_trip(self):
        Handler.mode = "ok"
        event = ScenarioInput("evt", "BTC", "Synthetic", "2026-01-01T00:00:00Z",
                              "2026-01-01T00:00:01Z", "fixture")
        adapter = SandboxedSimulationAdapter("mirofish-mock",
                    MiroFishLoopbackTransport(self.endpoint()))
        result = adapter.run(event)
        self.assertEqual(result.status, "UNVERIFIED")
        self.assertEqual(result.recommendation, "NO_SIGNAL")
        self.assertEqual(len(result.observations), 1)
    def test_rejects_remote_and_credential_urls(self):
        for url in ("https://example.com/api", "http://8.8.8.8/api",
                    "http://localhost:5001/api", "http://user:pass@127.0.0.1:5001/api",
                    "http://127.0.0.1:5001//evil", "http://127.0.0.1:5001/api?x=1"):
            with self.subTest(url=url), self.assertRaises(SimulationAdapterError):
                MiroFishLoopbackTransport(url)
    def test_rejects_non_success(self):
        Handler.mode = "error"
        try:
            with self.assertRaises(SimulationAdapterError):
                MiroFishLoopbackTransport(self.endpoint())({"event_id": "evt"})
        finally:
            Handler.mode = "ok"
    def test_response_size_budget(self):
        Handler.mode = "oversize"
        try:
            with self.assertRaises(SimulationAdapterError):
                MiroFishLoopbackTransport(self.endpoint(), max_response_bytes=100)(
                    {"event_id": "evt"})
        finally:
            Handler.mode = "ok"

if __name__ == "__main__":
    unittest.main()
