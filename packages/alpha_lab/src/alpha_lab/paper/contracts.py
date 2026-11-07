"""Immutable versioned contracts; Decimal economics and full UTC precision."""
from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import StrEnum
import hashlib
import json
import re

SCHEMA = "alpha-labs.paper.v1"


class ContractError(ValueError):
    pass


class Forbidden(PermissionError):
    pass


class Mode(StrEnum):
    RESEARCH = "research"
    BACKTEST = "backtest"
    SIMULATION = "simulation"
    SANDBOX = "broker_sandbox"
    LIVE = "live"


class Outcome(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"
    HALT = "HALT"
    UNSUPPORTED = "UNSUPPORTED"
    UNVERIFIED = "UNVERIFIED"


def identifier(value: str) -> str:
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,100}", value):
        raise ContractError("invalid identifier")
    return value


def number(value, *, minimum: str | None = None, positive: bool = False) -> Decimal:
    # Floating-point and boolean economics are deliberately excluded at the API.
    if type(value) not in (str, int, Decimal):
        raise ContractError("decimal string required")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ContractError("invalid decimal") from exc
    if (not result.is_finite() or result.adjusted() > 18
            or result.as_tuple().exponent < -18 or len(result.as_tuple().digits) > 36):
        raise ContractError("decimal outside supported precision/range")
    if positive and result <= 0 or minimum is not None and result < Decimal(minimum):
        raise ContractError("decimal outside permitted range")
    return result


def utc(value: str) -> datetime:
    if type(value) is not str or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", value
    ):
        raise ContractError("explicit UTC timestamp with at most microseconds required")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ContractError("invalid UTC timestamp") from exc


def timestamp(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ContractError("timezone required")
    return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def serialise(value):
    if is_dataclass(value):
        return serialise(asdict(value))
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (tuple, list)):
        return [serialise(v) for v in value]
    if isinstance(value, dict):
        return {k: serialise(v) for k, v in value.items()}
    return value


def canonical(value) -> str:
    return json.dumps(serialise(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class Principal:
    """Issued by the trusted identity adapter, never parsed from request JSON."""
    tenant: str
    subject: str
    role: str = "operator"

    def __post_init__(self):
        identifier(self.tenant)
        identifier(self.subject)
        if self.role not in {"operator", "viewer"}:
            raise ContractError("unsupported role")


@dataclass(frozen=True)
class Quote:
    instrument: str
    venue: str
    currency: str
    event_time: str
    received_time: str
    bid: Decimal
    ask: Decimal
    bid_size: Decimal
    ask_size: Decimal
    source_ref: str
    synthetic: bool
    asset_class: str = "crypto_spot"
    schema: str = SCHEMA

    def __post_init__(self):
        for value in (self.instrument, self.venue, self.currency, self.source_ref):
            identifier(value)
        if self.schema != SCHEMA or type(self.synthetic) is not bool:
            raise ContractError("unsupported quote contract")
        if self.asset_class not in {"crypto_spot", "us_equity", "us_etf", "forex", "futures"}:
            raise ContractError("unsupported asset class")
        if utc(self.event_time) > utc(self.received_time):
            raise ContractError("event follows receipt")
        for name in ("bid", "ask", "bid_size", "ask_size"):
            object.__setattr__(self, name, number(getattr(self, name), positive=True))
        if self.bid > self.ask:
            raise ContractError("crossed quote")

    def check(self, now: str, *, max_event_age_ms=5000, max_receipt_age_ms=5000,
              max_transport_ms=2000):
        # Revalidate even at consumption; no mutable dictionary bypass.
        self.__post_init__()
        decision, event, received = utc(now), utc(self.event_time), utc(self.received_time)
        for limit in (max_event_age_ms, max_receipt_age_ms, max_transport_ms):
            if type(limit) is not int or limit < 0:
                raise ContractError("invalid freshness limit")
        if received > decision:
            raise ContractError("receipt follows decision")
        if ((decision-event).total_seconds()*1000 > max_event_age_ms
                or (decision-received).total_seconds()*1000 > max_receipt_age_ms
                or (received-event).total_seconds()*1000 > max_transport_ms):
            raise ContractError("stale quote or excessive transport delay")

    @property
    def midpoint(self):
        return (self.bid + self.ask) / 2


@dataclass(frozen=True)
class Proposal:
    account_id: str
    instrument: str
    strategy_id: str
    direction: Outcome
    quantity: Decimal
    stop_price: Decimal
    idempotency_key: str
    order_type: str = "market"
    limit_price: Decimal | None = None
    schema: str = SCHEMA

    def __post_init__(self):
        for value in (self.account_id, self.instrument, self.strategy_id, self.idempotency_key):
            identifier(value)
        object.__setattr__(self, "direction", Outcome(self.direction))
        object.__setattr__(self, "quantity", number(self.quantity, positive=True))
        object.__setattr__(self, "stop_price", number(self.stop_price, positive=True))
        if self.order_type not in {"market", "limit"} or self.schema != SCHEMA:
            raise ContractError("unsupported proposal contract")
        if self.limit_price is not None:
            object.__setattr__(self, "limit_price", number(self.limit_price, positive=True))
        if self.order_type == "limit" and self.limit_price is None:
            raise ContractError("limit price required")


@dataclass(frozen=True)
class AgentAssessment:
    agent_id: str
    agent_version: str
    model_version: str
    prompt_version: str
    decision_time: str
    input_refs: tuple[str, ...]
    status: str
    summary: str
    supporting_evidence: tuple[str, ...] = ()
    conflicting_evidence: tuple[str, ...] = ()
    schema: str = SCHEMA

    def __post_init__(self):
        utc(self.decision_time)
        for value in (self.agent_id, self.agent_version, self.model_version, self.prompt_version):
            identifier(value)
        if self.schema != SCHEMA or self.status not in {"RECORDED", "UNVERIFIED", "FAILED"}:
            raise ContractError("invalid assessment contract")
        if type(self.summary) is not str or not 1 <= len(self.summary) <= 2000:
            raise ContractError("invalid assessment summary")
        for field in ("input_refs", "supporting_evidence", "conflicting_evidence"):
            values = getattr(self, field)
            if not isinstance(values, (tuple, list)) or len(values) > 20:
                raise ContractError("invalid evidence reference list")
            for ref in values:
                identifier(ref)
            object.__setattr__(self, field, tuple(values))


@dataclass(frozen=True)
class Decision:
    outcome: Outcome
    reasons: tuple[str, ...]
    proposal_hash: str
    quote_hash: str
    assessments: tuple[AgentAssessment, ...]
    estimated_entry_fee: Decimal = Decimal("0")
    planned_loss: Decimal = Decimal("0")
    simulated_execution_authorised: bool = False
    live_trading_authorised: bool = False
    schema: str = SCHEMA
