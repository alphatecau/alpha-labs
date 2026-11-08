# Signed archival evidence — security boundary

The `phase1_signed_archive.verify_signed_archive` validator hashes the **actual bytes** of supplied archive and research files, verifies a signed manifest with Ed25519, checks archive identity, and rejects archive capture dates after the historical decision.

**Required dependency:** `cryptography` (Ed25519 support). The unit test is skipped when it is not installed; therefore a green CI run does **not** prove cryptographic verification was executed unless the test log confirms it ran. Before integration or promotion, install `cryptography` in the offline research test environment and require the test to execute without skipping.

**Trust model:** The caller must provision a trusted archive-provider public key using a separate authenticated channel. Passing an arbitrary key alongside a manifest only proves the manifest was signed by that arbitrary key. Signed content does not independently authenticate the original archive timestamp or the claimed publication date. Trusted timestamp authority, transparency log or independently authenticated archival service records are still required.

The implementation reads entire files into memory and is limited to controlled, size-bounded research fixtures. For large or untrusted inputs, implement size limits and streaming SHA-256 before accepting external archives.

No genuine provider archive, credential or historical data has been authenticated. This module is **research-only** and returns `eligible_for_strategy_promotion=False`. No broker integration, deployment or live trading.
