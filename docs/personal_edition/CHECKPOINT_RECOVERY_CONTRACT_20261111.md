# Authenticated checkpoint recovery contract

Research-only, opt-in runtime gate. Supply `trusted_checkpoint` (the HMAC envelope) and `checkpoint_secret` (independent key bytes, minimum 32 bytes) together when constructing `PaperRuntime`. Neither is loaded from the repository, journal database, nor environment automatically.

- If both values are supplied, recovery verifies the MAC and requires the journal sequence and head to match exactly before replay.
- If only one is supplied, recovery fails closed.
- If neither is supplied, legacy journal hash-chain verification remains in effect; **this does not establish rollback protection**.
- After any legitimate append, the previous envelope becomes stale. An authorised external checkpoint service must publish a new authenticated envelope atomically with its own monotonic sequence policy before the next trusted restart.
- A static HMAC envelope cannot prevent rollback to a previous legitimately signed journal/checkpoint pair. An independently controlled append-only or monotonic external anchor is required.
- Key custody, checkpoint persistence, recovery after crash between journal append and external anchor update, and rotation/revocation are not implemented. Do not store secrets in GitHub or commit real checkpoints.
- No live trading, brokers, deployment, or credentials are changed by this research branch.

**Acceptance:** CI, crash-window testing, secure anchor integration, rollback and key-rotation adversarial tests, independent security review.
