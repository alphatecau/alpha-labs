"""Broker-neutral capability boundary. No exchange or brokerage order transport."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .contracts import Mode


@dataclass(frozen=True)
class BrokerCapabilities:
    provider: str
    read_only: bool = True
    simulation: bool = False
    sandbox: bool = False
    live: bool = False
    withdrawals: bool = False


class ReadOnlyBroker(Protocol):
    capabilities: BrokerCapabilities
    def health(self) -> bool: ...


class SimulatedBroker:
    capabilities = BrokerCapabilities("local-simulation", simulation=True)

    def __init__(self):
        self.connected = True

    def health(self):
        return self.connected is True


class UnavailableBroker:
    """Interfaces only; Binance/IBKR eligibility and sandboxes unverified."""
    def __init__(self, provider: str):
        if provider not in {"binance", "interactive-brokers"}:
            raise ValueError("unknown provider")
        self.capabilities = BrokerCapabilities(provider)

    def health(self):
        return False

    def submit(self, *args, **kwargs):
        raise PermissionError("broker order submission is disabled in every mode")


def execution_transport(mode: Mode):
    if Mode(mode) != Mode.SIMULATION:
        raise PermissionError("only local simulated execution is implemented")
    return SimulatedBroker()
