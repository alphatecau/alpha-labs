import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from alpha_lab.mirofish_async import MiroFishAsyncClient
from alpha_lab.mirofish_sandbox_http import MiroFishSandboxHTTP
from alpha_lab.simulation_adapter import SimulationAdapterError

class MockMiroFish(BaseHTTPRequestHandler):
    calls = []
    def respond(self, data):
        raw = json.dumps({"success": True, "data": data}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.calls.append((self.path, body))
        if self.path == "/api/simulation/create":
            self.respond({"simulation_id": "sim_1", "status": "created"})
        elif self.path == "/api/simulation/prepare":
            self.respond({"simulation_id": "sim_1", "task_id": "task_1", "status": "preparing"})
        elif self.path == "/api/simulation/prepare/status":
            self.respond({"status": "completed", "progress": 100})
        elif self.path == "/api/simulation/start":
            self.respond({"runner_status": "running"})
        elif self.path == "/api/report/generate":
            self.respond({"task_id": "task_2", "status": "generating"})
        elif self.path == "/api/report/generate/status":
            self.respond({"status": "completed"})
        else:
            self.send_error(404)
    def do_GET(self):
        self.calls.append((self.path, None))
        if self.path == "/api/simulation/sim_1/run-status":
            self.respond({"runner_status": "completed", "current_round": 3})
        else:
            self.send_error(404)
    def log_message(self, *_):
        pass

class AsyncLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), MockMiroFish)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
    def setUp(self):
        MockMiroFish.calls = []
        self.client = MiroFishAsyncClient(MiroFishSandboxHTTP(
            "http://127.0.0.1:%d" % self.server.server_port))
    def test_full_mock_async_lifecycle(self):
        state = self.client.create("proj_1")
        self.assertEqual(state.simulation_id, "sim_1")
        task = self.client.prepare(state.simulation_id)
        self.assertEqual(task["task_id"], "task_1")
        self.assertEqual(self.client.prepare_status(task_id="task_1")["status"], "completed")
        self.assertEqual(self.client.start("sim_1", max_rounds=3)["runner_status"], "running")
        self.assertEqual(self.client.run_status("sim_1")["runner_status"], "completed")
        report = self.client.generate_report("sim_1")
        self.assertEqual(self.client.report_status(task_id=report["task_id"])["status"], "completed")
        self.assertEqual(len(MockMiroFish.calls), 7)
        self.assertEqual(MockMiroFish.calls[3][1]["enable_graph_memory_update"], False)
    def test_rejects_external_urls(self):
        for url in ("http://example.com:5001", "http://8.8.8.8:5001",
                    "http://localhost:5001", "http://127.0.0.1:5001/evil"):
            with self.subTest(url=url), self.assertRaises(SimulationAdapterError):
                MiroFishSandboxHTTP(url)
    def test_rejects_bad_id_and_rounds(self):
        with self.assertRaises(SimulationAdapterError):
            self.client.create("../secret")
        with self.assertRaises(SimulationAdapterError):
            self.client.start("sim_1", max_rounds=100)
    def test_no_automatic_polling(self):
        self.client.prepare("sim_1")
        self.assertEqual(len(MockMiroFish.calls), 1)
    def test_rejects_unapproved_api_path(self):
        with self.assertRaises(SimulationAdapterError):
            MiroFishSandboxHTTP("http://127.0.0.1:5001")("GET", "/admin", None)

if __name__ == "__main__":
    unittest.main()
