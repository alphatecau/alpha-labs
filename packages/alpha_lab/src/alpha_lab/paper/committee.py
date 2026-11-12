"""Bounded specialist workflow; deterministic fixtures, no model/tool authority.

Unavailable fundamental/news/LLM integrations are explicitly UNVERIFIED. These
records are an orchestration contract, not fourteen independently trained models.
"""
from __future__ import annotations

import asyncio
from typing import Protocol

from .contracts import AgentAssessment, Outcome, Proposal, Quote, digest

ROLES = (
    "orchestrator", "market_intelligence", "technical", "quantitative",
    "fundamental", "news", "bull", "bear", "sceptic", "portfolio", "decision",
    "execution", "risk_monitoring", "performance",
)
FIXTURE_STRATEGY = "synthetic-contract-v1"
REJECTED = frozenset({"ema-12-48", "strategy-v0.8", "strategy-v0.9",
                      "A_1d", "A_1d_neighbor", "A_4h", "A_4h_neighbor",
                      "B_4h", "B_4h_neighbor", "exploratory-trend", "exploratory-rotation"})


class ResearchAgent(Protocol):
    """Future bounded adapters receive data, never store/broker/policy handles."""
    async def assess(self, input_json: str) -> AgentAssessment: ...


async def bounded_research_assessment(agent: ResearchAgent, input_json: str,
                                      *, timeout_seconds=2) -> AgentAssessment:
    """Optional research adapter boundary; one attempt, no privileged tools.

    Caller supplies a bounded serialised research context. The result can be
    journalled but is never an execution/risk authorisation input in v0.12.
    """
    if not 0 < timeout_seconds <= 5 or type(input_json) is not str or len(input_json) > 32_768:
        raise ValueError("unbounded research request")
    result = await asyncio.wait_for(agent.assess(input_json), timeout=timeout_seconds)
    if not isinstance(result, AgentAssessment) or result.agent_id not in ROLES:
        raise ValueError("invalid specialist response")
    result.__post_init__()
    return result


def evidence_status(strategy: str) -> str:
    if strategy in REJECTED:
        return "REJECTED"
    if strategy == FIXTURE_STRATEGY:
        return "SYNTHETIC_CONTRACT_FIXTURE_ONLY"
    return "UNVERIFIED"


def quantitative_signal(quote: Quote) -> Outcome:
    # Deliberately artificial software-test rule; no real-market alpha claim.
    return Outcome.LONG if quote.midpoint >= 100 else Outcome.FLAT


def assess(proposal: Proposal, quote: Quote, now: str, *, exposure: str) -> tuple[AgentAssessment, ...]:
    refs = ("sha256:"+digest(quote), "strategy-sha256:"+digest(proposal.strategy_id))
    texts = {
        "orchestrator": "Local simulation cycle; external tools and model calls disabled.",
        "market_intelligence": "Causal quote contract checked; depth is a synthetic scenario.",
        "technical": f"Fixture threshold signal: {quantitative_signal(quote)}.",
        "quantitative": f"Strategy evidence: {evidence_status(proposal.strategy_id)}.",
        "fundamental": "Fundamental provider absent; no inferred company or economic facts.",
        "news": "Verified news provider absent; external text cannot authorise actions.",
        "bull": "Fixture LONG thesis: artificial midpoint threshold is met.",
        "bear": "Costs, price gaps and absent market validation oppose any real trade.",
        "sceptic": "AI consensus and synthetic outcomes do not establish an edge.",
        "portfolio": f"Marked simulated exposure: {exposure}; correlation model unverified.",
        "decision": "Deterministic strategy/mode/evidence gates decide; no voting override.",
        "execution": "Only the transactional simulation service may create order records.",
        "risk_monitoring": "Policy is fixed outside agent inputs; durable HALT has priority.",
        "performance": "Journal records assumed costs; empirical execution and alpha unverified.",
    }
    return tuple(AgentAssessment(
        agent_id=role, agent_version="0.12.0", model_version="deterministic-python/0.12",
        prompt_version="none", decision_time=now, input_refs=refs,
        status="UNVERIFIED" if role in {"fundamental", "news"} else "RECORDED",
        summary=texts[role],
        supporting_evidence=refs if role not in {"fundamental", "news"} else (),
        conflicting_evidence=("independent-market-evidence-missing",)
        if role in {"bear", "sceptic", "quantitative"} else (),
    ) for role in ROLES)


def gate(proposal: Proposal, quote: Quote) -> tuple[Outcome, tuple[str, ...]]:
    status = evidence_status(proposal.strategy_id)
    if status == "REJECTED":
        return Outcome.UNVERIFIED, ("HISTORICAL_REJECTION_PRESERVED",)
    if status != "SYNTHETIC_CONTRACT_FIXTURE_ONLY":
        return Outcome.UNVERIFIED, ("INDEPENDENT_STRATEGY_EVIDENCE_MISSING",)
    if (not quote.synthetic or quote.instrument != "TEST/AUD"
            or quote.venue != "synthetic" or quote.currency != "AUD"):
        return Outcome.UNVERIFIED, ("FIXTURE_SCOPE_MISMATCH",)
    if quote.asset_class != "crypto_spot" or proposal.direction == Outcome.SHORT:
        return Outcome.UNSUPPORTED, ("INSTRUMENT_OR_SHORT_EXECUTION_UNSUPPORTED",)
    signal = quantitative_signal(quote)
    if proposal.direction in {Outcome.FLAT, Outcome.HALT}:
        return proposal.direction, ("NO_ENTRY_REQUESTED",)
    if proposal.direction != signal:
        return Outcome.FLAT, ("PROPOSAL_DISAGREES_WITH_DETERMINISTIC_SIGNAL",)
    return signal, ()
