# v0.5 signed worker — opt-in integration

This standalone worker reads the fingerprint-enrolled Ed25519 public keys from the local v0.5 keyring and verifies device-bound, expiring signatures before executing **only** repo_status/repo_log for alpha-labs/Q3HASH. It uses a distinct label `termux-bridge-v5-signed` and a private SQLite ledger. No private signer key is ever placed on Android.

Default invocation `python worker_v5.py --device YOUR_DEVICE_ID` verifies only; `--execute` performs read-only operations. **Do not activate yet.** First complete independent signer enrolment, Android dependency verification, negative tests, crash recovery tests and supervised rollback acceptance. The v0.3 agent remains unchanged.

The ledger reserves the issue and nonce before execution. A crash during execution intentionally prevents automatic replay; operator reconciliation is required. Completed receipts can be retried without re-execution. The worker polls at most 100 open issues and requires a further pagination design for larger backlogs. Do not enable unrestricted shell or use GitHub issue labels as an alternative to signatures.

## Ambiguous receipt publication

Before attempting a GitHub receipt, the ledger durably records `publishing_success` or `publishing_failed`. If the network or process fails after this transition, the worker deliberately does **not** retry automatically: GitHub may already have accepted the comment. Operators must inspect the issue and ledger and reconcile manually. This prioritises no duplicate publication over automatic delivery. A crash before this transition leaves the terminal receipt eligible for retry. A crash during read-only execution remains `reserved` and is never automatically re-executed.
