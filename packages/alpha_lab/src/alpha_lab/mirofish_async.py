"""MiroFish API lifecycle adapter (research-only, nonblocking).

Requires an EXISTING sandbox project and graph; it does not create or upload
seed material, install MiroFish, or run models. Explicit calls avoid automatic
long-running/paid work. Transport must be loopback-only and separately isolated.
Upstream route contract inspected: 666ghj/MiroFish backend/app/api/simulation.py.
"""
from dataclasses import dataclass
from typing import Any, Callable
from .simulation_adapter import SimulationAdapterError

@dataclass(frozen=True)
class MiroFishLifecycle:
    simulation_id: str
    project_id: str
    state: str

class MiroFishAsyncClient:
    def __init__(self, request_json: Callable[[str, str, dict | None], dict]):
        if not callable(request_json):
            raise SimulationAdapterError("Explicit sandbox request transport required")
        self._request = request_json

    def _call(self, method: str, path: str, payload: dict | None = None) -> dict:
        try:
            response = self._request(method, path, payload)
        except Exception as exc:
            raise SimulationAdapterError("MiroFish request failed") from exc
        if not isinstance(response, dict) or response.get("success") is not True:
            raise SimulationAdapterError("MiroFish rejected request")
        data = response.get("data")
        if not isinstance(data, dict):
            raise SimulationAdapterError("MiroFish response missing data")
        return data

    @staticmethod
    def _identifier(value: str) -> str:
        if not isinstance(value, str) or not 1 <= len(value) <= 100 or not all(
            c.isascii() and (c.isalnum() or c in "_-") for c in value
        ):
            raise SimulationAdapterError("Invalid MiroFish identifier")
        return value

    def create(self, project_id: str) -> MiroFishLifecycle:
        project_id = self._identifier(project_id)
        data = self._call("POST", "/api/simulation/create", {
            "project_id": project_id, "enable_twitter": True, "enable_reddit": False})
        simulation_id = self._identifier(data.get("simulation_id"))
        return MiroFishLifecycle(simulation_id, project_id, "created")

    def prepare(self, simulation_id: str) -> dict:
        simulation_id = self._identifier(simulation_id)
        data = self._call("POST", "/api/simulation/prepare", {
            "simulation_id": simulation_id, "parallel_profile_count": 1,
            "force_regenerate": False})
        if data.get("task_id") is not None:
            self._identifier(data["task_id"])
        return data

    def prepare_status(self, *, task_id: str | None = None,
                       simulation_id: str | None = None) -> dict:
        if not task_id and not simulation_id:
            raise SimulationAdapterError("A task or simulation ID is required")
        payload = {}
        if task_id:
            payload["task_id"] = self._identifier(task_id)
        if simulation_id:
            payload["simulation_id"] = self._identifier(simulation_id)
        return self._call("POST", "/api/simulation/prepare/status", payload)

    def start(self, simulation_id: str, *, max_rounds: int = 3) -> dict:
        if not isinstance(max_rounds, int) or not 1 <= max_rounds <= 5:
            raise SimulationAdapterError("Sandbox permits 1-5 rounds only")
        return self._call("POST", "/api/simulation/start", {
            "simulation_id": self._identifier(simulation_id),
            "platform": "twitter", "max_rounds": max_rounds,
            "enable_graph_memory_update": False, "force": False})

    def run_status(self, simulation_id: str) -> dict:
        return self._call("GET", "/api/simulation/" +
                          self._identifier(simulation_id) + "/run-status")

    def report_status(self, *, task_id: str) -> dict:
        return self._call("POST", "/api/report/generate/status", {
            "task_id": self._identifier(task_id)})

    def generate_report(self, simulation_id: str) -> dict:
        return self._call("POST", "/api/report/generate", {
            "simulation_id": self._identifier(simulation_id),
            "force_regenerate": False})
