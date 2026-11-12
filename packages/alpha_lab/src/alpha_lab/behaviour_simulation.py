"""Bounded, deterministic, research-only behavioural scenario prototype.

This is NOT MiroFish or a price prediction model. No network, broker or LLM access.
Outputs are synthetic scenario narratives, not probabilities or trading signals.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
import random
from typing import Sequence

PERSONAS = (
    ("institutional", "liquidity and macroeconomic risk"),
    ("retail", "headlines and social sentiment"),
    ("market_maker", "inventory and liquidity"),
    ("risk_manager", "downside and uncertainty"),
    ("sceptic", "contradictory evidence"),
)

@dataclass(frozen=True)
class ScenarioInput:
    event_id: str
    asset: str
    headline: str
    observed_at_utc: str
    information_cutoff_utc: str
    source_id: str

@dataclass(frozen=True)
class ScenarioResult:
    event_id: str
    asset: str
    input_sha256: str
    seed: int
    rounds: int
    agents: int
    synthetic_reactions: tuple
    status: str = "UNVERIFIED"
    recommendation: str = "NO_SIGNAL"

def simulate(event: ScenarioInput, *, seed: int = 0, rounds: int = 3,
             agents: int = 5) -> ScenarioResult:
    """Produce synthetic, bounded reactions for research plumbing tests only."""
    from datetime import datetime, timezone
    if not all((event.event_id, event.asset, event.headline,
                event.source_id, event.observed_at_utc, event.information_cutoff_utc)):
        raise ValueError("All event provenance fields are required")
    def parse_utc(value):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.utcoffset() != timezone.utc.utcoffset(dt):
            raise ValueError("Timestamps must be UTC with an explicit timezone")
        return dt
    if parse_utc(event.observed_at_utc) > parse_utc(event.information_cutoff_utc):
        raise ValueError("Event observed after information cutoff (look-ahead leakage)")
    if not 1 <= agents <= 10 or not 1 <= rounds <= 5:
        raise ValueError("Prototype limits: 1-10 agents and 1-5 rounds")
    if len(event.headline) > 2000:
        raise ValueError("Headline exceeds 2000 characters")
    canonical = json.dumps(asdict(event), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    rng = random.Random(seed)
    reactions = []
    labels = ("cautious", "mixed", "optimistic")
    for round_number in range(1, rounds + 1):
        for agent_number in range(agents):
            persona, concern = PERSONAS[agent_number % len(PERSONAS)]
            reactions.append({
                "round": round_number,
                "agent_id": agent_number,
                "persona": persona,
                "focus": concern,
                "synthetic_stance": labels[rng.randrange(len(labels))],
                "evidence": "NONE — synthetic fixture only",
            })
    return ScenarioResult(event.event_id, event.asset, digest, seed, rounds,
                          agents, tuple(reactions))
