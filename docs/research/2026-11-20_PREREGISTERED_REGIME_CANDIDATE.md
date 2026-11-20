# Preregistration — candidate R1 (NOT evaluated)

Status: protocol proposal only. No dataset has been unsealed and no performance is claimed.
Comparator: unchanged EMA(12,48) long/flat, same initial capital, fill timing, and matched passive benchmark.

## Hypothesis and frozen rule
R1 is a regime-aware *filter* of the EMA(12,48) long signal, not a replacement baseline.
At each completed hourly bar t, use only bars ending at or before t:
- Long permitted only when EMA12(t) > EMA48(t), close(t) > SMA200(t), and
  48-bar realised log-return volatility is <= the 75th percentile of the preceding
  720 *completed* 48-bar volatility observations (exclude current observation).
- Otherwise flat. Warm up until all inputs exist. No shorts, leverage, or intrabar signals.
- Orders at the next bar open, with the baseline's 20% initial-cash maximum allocation.
- No parameter search or optimisation of 12/48/200/48/720/75 after registration.

## Costs and acceptance
Use 10 bps fees + 10 bps adverse slippage each side as the historical reference
assumption, then independently rerun at 20 + 20 bps each side. Validate
alternative venue-specific actual fees/spread observations before any economic claim.
Report quote-currency realised fees, estimated exit fees, inventory, cash,
conservative liquidation NAV, return, max drawdown, trade count, fold-by-fold
excess over passive and frozen EMA, and uncertainty. No AUD conversion without
timestamped independently sourced FX and explicit FX costs.
Fail candidate if accounting fails, if cost stress breaks viability, or if
positive excess is not robust across independently designated forward folds.

## Sealed prospective holdout
Previously inspected 2023–2025 partitions are NOT sealed and may only support
engineering, training or descriptive comparison. The reserved 2027-01-01 through
2028-01-01 UTC window must remain unread until an independent custodian:
(1) records immutable dataset/venue/transform/source SHA-256 manifests;
(2) timestamps and signs this preregistration and its source commit;
(3) verifies no researcher access to reserved outcomes;
(4) enforces one-time unseal and immutable evaluation logging.
A GitHub commit alone is NOT an independent seal. No access to future data or
backfill of this window is authorised by this document.

## Blockers
No independently sealed evaluation, no verified execution-quality historical
bid/ask observations, no venue fee calibration, no demonstrated R1 performance.
The comparator implements the registered signal. Independent walk-forward evaluation and prospective custody remain pending.
