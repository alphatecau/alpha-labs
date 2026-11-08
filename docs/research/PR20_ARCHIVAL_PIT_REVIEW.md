# PR #20 — Archival PIT review

Reviewed original head `6a6dc6ee4793a9d391596707dd119f1f6648abec`.

- Research CI: https://github.com/alphatecau/alpha-labs/actions/runs/42481664286 — PASS.
- Sites CI: https://github.com/alphatecau/alpha-labs/actions/runs/42481664426 — PASS.
- The validator correctly separates historical publication, archive capture and later research acquisition timestamps and rejects inconsistent supplied chronology.
- Tests cover eight synthetic chronology scenarios; these are not authentic archive records.

## Material limitations
1. **P1: caller-supplied digest equality is not byte verification.** The module does not open an archive or research file, compute their SHA-256 digests, or verify archive capture metadata cryptographically. Updated its docstring to avoid implying otherwise.
2. **P1: caller-supplied archive timestamp is not proof.** A fabricated old capture time can satisfy the function. Independent archive provenance and immutable capture evidence are mandatory.
3. **P1: publication assertions remain unauthenticated.** The original publisher and earliest-publication time must be independently established before historical strategy promotion.
4. **P2: no integration into the full ETF evidence ingestion pipeline.** This is a separate reusable gate, not a complete end-to-end market-data audit.

## Disposition
**CONDITIONAL — RESEARCH ONLY.** The initial head passed CI. Recheck CI after review/documentation commits. Do not merge until byte-level integrity and archive authenticity requirements are independently reviewed or explicitly scoped as non-promotional research limitations. PR #17 remains separate. No deployment, broker integration or live trading.
