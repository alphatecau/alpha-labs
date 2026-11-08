"""Isolated adapter contract for genuine external multi-agent simulation services.

Research only. No built-in HTTP transport, credentials, trading, or production hooks.
A caller must supply a reviewed, sandboxed transport implementation.
"""
from dataclasses import dataclass
from typing import Callable, Mapping, Any
from .behaviour_simulation import ScenarioInput
import hashlib
import json

@dataclass(frozen=True)
class AdapterPolicy:
    max_agents: int = 10
    max_rounds: int = 5
    max_response_bytes: int = 100_000

@dataclass(frozen=True)
class ProviderResult:
    event_id: str
    provider: str
    status: str
    recommendation: str
    observations: tuple
    response_sha256: str

class SimulationAdapterError(ValueError):
    pass

class SandboxedSimulationAdapter:
    """Fail-closed boundary; external provider access is injected, never implicit.

    The transport should run out of process with egress allowlisting, hard
    timeout, token quota, nonprivileged identity and zero broker permissions.
    """
    def __init__(self, provider: str, transport: Callable[[Mapping[str, Any]], Mapping[str, Any]],
                 policy: AdapterPolicy = AdapterPolicy()):
        if not provider or not callable(transport):
            raise SimulationAdapterError("Provider and callable transport required")
        if not (1 <= policy.max_agents <= 10 and 1 <= policy.max_rounds <= 5
                and 1 <= policy.max_response_bytes <= 100_000):
            raise SimulationAdapterError("Invalid adapter policy")
        self.provider = provider
        self.transport = transport
        self.policy = policy

    def run(self, event: ScenarioInput, *, agents: int = 5, rounds: int = 3) -> ProviderResult:
        # Validate temporal provenance using the established research contract.
        from .behaviour_simulation import simulate
        simulate(event, agents=1, rounds=1)
        if not 1 <= agents <= self.policy.max_agents or not 1 <= rounds <= self.policy.max_rounds:
            raise SimulationAdapterError("Simulation exceeds approved budget")
        request = {"event_id": event.event_id, "asset": event.asset,
                   "headline": event.headline, "source_id": event.source_id,
                   "observed_at_utc": event.observed_at_utc,
                   "information_cutoff_utc": event.information_cutoff_utc,
                   "agents": agents, "rounds": rounds, "mode": "RESEARCH_ONLY"}
        try:
            response = self.transport(request)
        except Exception as exc:
            raise SimulationAdapterError("Simulation provider unavailable") from exc
        if not isinstance(response, dict):
            raise SimulationAdapterError("Provider response must be an object")
        try:
            raw = json.dumps(response, sort_keys=True, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise SimulationAdapterError("Invalid provider response") from exc
        if len(raw) > self.policy.max_response_bytes:
            raise SimulationAdapterError("Provider response too large")
        if response.get("event_id") != event.event_id:
            raise SimulationAdapterError("Provider event mismatch")
        observations = response.get("observations")
        if not isinstance(observations, list) or len(observations) > agents * rounds:
            raise SimulationAdapterError("Invalid observation count")
        for item in observations:
            if not isinstance(item, dict) or not isinstance(item.get("persona"), str) or not isinstance(item.get("narrative"), str):
                raise SimulationAdapterError("Invalid observation structure")
            if len(item["narrative"]) > 4000:
                raise SimulationAdapterError("Observation exceeds length limit")
        # Never trust provider trade instructions, probabilities or validation claims.
        return ProviderResult(event.event_id, self.provider, "UNVERIFIED", "NO_SIGNAL",
                              tuple({"persona": i["persona"], "synthetic_narrative": i["narrative"]}
                                    for i in observations), hashlib.sha256(raw).hexdigest())
