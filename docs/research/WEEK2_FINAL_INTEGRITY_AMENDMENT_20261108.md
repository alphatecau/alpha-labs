# Week 2 final evaluation — integrity incident and pre-evaluation amendment

**Incident:** The first final-evaluation workflow failed with `ValueError: FROZEN DATA CHANGED: BTCUSDT` before any market strategy replay. The initial code required an exact SHA-256 match of the *regenerated* JSON manifest. This is not a stable identity: `build_dataset()` embeds `retrieved_at_utc=datetime.now(UTC).isoformat()` in the manifest. Re-fetching the same verified source archives creates a new manifest hash despite unchanged candle data. The first run did not produce strategy returns.

**Correction (before viewing any later-period strategy returns):**
- Preserve all three previously frozen CSV SHA-256 digests and the exact strategy source blob hashes. They are unchanged.
- Preserve original JSON manifest SHA-256 digests as the historical acquisition receipts, not as byte-for-byte requirements for a later re-download.
- Require `verify_dataset(csv, manifest)`, which independently checks every cached source archive against its official checksum, parses all source rows and verifies the canonical curated CSV digest.
- Require exact frozen symbol, period, 7,296 candle count and CSV digest for each market. Require verified manifest provenance and the recorded original acquisition receipts.
- Record regenerated manifest SHA-256 as a new execution receipt; it is expected to differ because retrieval timestamp changes. Never substitute it for the original receipt.
- Do not tune strategy parameters, rerun after inspecting results, weaken safety flags, merge or deploy.

**Reason for fail-closed stop:** A volatile retrieval timestamp was mistakenly included in the byte-level lock. This amendment fixes only the manifest reproducibility contract. Any mismatch in actual CSV, original archive checksums, source code or 7,296 candle count still aborts the evaluation.

**Statistical decision unchanged:** no independently sealed prospective holdout; nine comparisons and prior adaptive selection remain. Strategy decision INCONCLUSIVE regardless of modelled returns.
