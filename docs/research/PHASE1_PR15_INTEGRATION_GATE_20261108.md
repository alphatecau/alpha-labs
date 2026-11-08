# Phase 1 / PR #15 integration gate — 2026-11-08

Status: **BLOCKED FOR MERGE; RESEARCH ONLY**.

## Pinned inputs
- Main after PR #15 merge: `ac2ae5046ca0d17d68c6ab372e9aa92eb04b5cf0`.
- Phase 1 integrated audit source: `30ce4530ca7c21c3c209e6dc4a57365d528f2b7c`.
- Original comparison: 111 commits ahead, 1 behind; merge base `9d705bd1982396b19006b9abd3ec8b6a254f2972`.
- This isolated review branch starts at the Phase 1 source. It does **not** yet contain the PR #15 merge commit.

## Audit observations
1. Phase 1 `phase1_evidence.py` includes experiment-record hashing, hourly UTC grid checks, signal-availability ordering, execution-cost shortfall and lagged volatility weights. These are source-inspection observations, not end-to-end validation.
2. `execution_cost_bridge` explicitly cannot separate spread from impact using only a reference midpoint and fill price; empirical spread/impact calibration remains unverified.
3. `lagged_volatility_weights` uses historical prices and caps weights; verify benchmark alignment against strategy timing and risk exposures in adversarial tests.
4. PR #15's chronological OOS screen is merged on main; duplication/conflict with Phase 1 promotion gates must be resolved. No strategy promotion is authorised.
5. The combined-status query returned no statuses and PR-filtered workflow lookup returned no runs for Phase 1 SHA. These limited queries **do not establish** the full Actions/check-run result.

## Required acceptance before merge
- [ ] Reconcile merged PR #15 into this isolated branch with reviewed conflict resolution, retaining original research branches untouched.
- [ ] Select one fail-closed evidence-promotion interface and test conflicting/missing evidence inputs.
- [ ] Run unit and adversarial tests on the exact reconciled SHA; capture workflow links, logs, environment, test counts and hashes.
- [ ] Independently reconcile cash/NAV, costs and risk-matched benchmark outputs with negative fixtures.
- [ ] Verify market data point-in-time provenance, publication lag, calendars, corporate actions, survivorship and holdout isolation.
- [ ] Obtain independent technical/security/statistical review before considering merge.

No merge, deployment, live trading, broker integration, secrets, capital release or profitability claims. See issue #16.
