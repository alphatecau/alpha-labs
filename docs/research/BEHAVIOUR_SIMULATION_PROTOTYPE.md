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
