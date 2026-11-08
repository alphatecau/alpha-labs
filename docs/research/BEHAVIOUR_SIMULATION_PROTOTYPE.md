# Alpha Labs — behavioural scenario prototype

Status: **EXPERIMENTAL / UNVERIFIED**. Related: #13.

## Scope
A deterministic, standard-library-only fixture generator for scenario research
plumbing. This is **not** an implementation of MiroFish, a realistic crowd model,
a calibrated forecast, a profitable strategy, or a trading signal. Its random
stances have no relationship to the supplied headline. Do not use them to trade.

## Architecture decision
Build an independent adapter interface before considering an upstream MiroFish
integration. Upstream MiroFish is AGPL-3.0, uses OASIS, an LLM endpoint and Zep
Cloud. Review licence obligations, dependencies, privacy, prompt injection and
costs before importing or running upstream code. No upstream code is copied.

## Research gates
1. **Phase 0**: Review upstream licence/security, document point-in-time source
   contracts, API budgets, and test coverage.
2. **Phase 1**: Run offline deterministic fixtures, then design a separately
   sandboxed provider adapter; enforce quotas, provenance and failure isolation.
3. **Phase 2**: Pre-register an evaluation comparing quantitative-only baseline
   against augmented model using point-in-time event snapshots, walk-forward
   splits, sealed holdout, multiple seeds, ablations and realistic costs.
4. **Phase 3**: Prospective paper-only shadow runs with independent risk controls.

## Contract
`ScenarioInput` requires event ID, asset, headline, observed UTC time, information
cutoff UTC time, and source ID. Events observed after the cutoff are rejected.
`simulate` limits agents to 1–10 and rounds to 1–5. Output is always
`UNVERIFIED` and `NO_SIGNAL`. It makes no network requests and cannot place orders.

## Local verification
```sh
python -m pip install -e .
python -m unittest discover -s tests/unit -p 'test_behaviour_simulation.py' -v
```

## Outstanding
- CI result not yet observed
- No real MiroFish integration, LLM, Zep or OASIS execution
- No market data, performance claims, backtests or live trading
- No frontend integration, deployment, merge or production changes


## External provider adapter (development branch)
`alpha_lab.simulation_adapter.SandboxedSimulationAdapter` is a transport-injected
integration boundary, not an installed MiroFish client. A reviewed transport
must supply a bounded response object containing the matching `event_id` and
`observations: [{persona: string, narrative: string}]`. Provider-generated
trade recommendations and confidence scores are deliberately discarded.
Responses remain `UNVERIFIED` and `NO_SIGNAL`.

**Before connecting a real provider:** implement an out-of-process worker with
network egress allowlisting, authentication, TLS, timeouts, concurrency/token
quotas, prompt-injection filtering, content provenance, isolated memory, secret
management and audit logs. Do not pass broker credentials or privileged tools.
Review MiroFish's actual API protocol and licence first; this generic contract
is not asserted to be compatible with its current endpoints.

Run:
```sh
PYTHONPATH=packages/alpha_lab/src python -m unittest discover -s tests/unit -p 'test_simulation_adapter.py' -v
```
CI status for the adapter commit must be verified separately from the earlier
successful PR workflow.


## MiroFish loopback transport — restricted test boundary
`alpha_lab.mirofish_transport.MiroFishLoopbackTransport` implements a
loopback-only HTTP POST transport. It rejects DNS hostnames, public IPs, HTTPS
endpoints, embedded credentials, redirects (any non-200), unexpected content
types, oversized responses and invalid JSON. Tests use an in-process local
mock server only. No genuine MiroFish backend has been launched or contacted.

**Compatibility is not verified.** The upstream README confirms a backend
on localhost port 5001 but does not establish a synchronous simulation endpoint
with this adapter's JSON schema. Confirm the actual upstream route, async job
lifecycle, request and response schemas against a pinned upstream commit before
attempting a live backend test. If incompatible, write an explicit translation
worker; do not point the transport at an arbitrary MiroFish endpoint.

This code restricts its own network destination but **does not create an OS
sandbox**. Real execution requires an isolated container/VM, blocked external
egress except approved LLM/Zep endpoints, credentials scoped to the worker,
resource quotas, timeout enforcement, and no exchange or broker credentials.
