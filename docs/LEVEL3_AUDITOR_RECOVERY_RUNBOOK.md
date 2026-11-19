# Level 3 auditor checkpoint recovery — staging runbook

Status: **STAGING ONLY / PRODUCTION NO-GO**. This document does not authorise trading.

## Established evidence (20 November 2026)

- Neon project `frosty-river-38771873`, branch `br-solitary-hall-a7h0lefq`, database `level3custody`.
- Two synthetic staging audit events, sequence 1 `claimed` and 2 `complete`.
- Verified audit head: `aadf7076b832da487534fd9cd94371c2250046899f554d44118e5e207eda5ca3`.
- Independently signed local/Drive checkpoint SHA-256: `01dcf7338d982375410c88786f32d3c10fa848e80460fe3d107ac23671448d1`.
- Auditor Ed25519 public key: `e48e95f7e6024b162b562b0a1e952150b2d810774948229bdc39fe03aa5986c4`.
- User confirmed Android local and Drive byte-for-byte readback PASS.
- No WORM or immutable-retention claim.

## Routine read-only verification

Run from the Android repository checkout:

```sh
python -m tools.level3_staging.auditor_checkpoint_verify
```

This requires the existing local checkpoint and independently configured `auditor:` rclone remote. It does not need the signing-key passphrase or Neon DSN.

## After an interruption or ambiguous write

1. **STOP.** Do not rerun the checkpoint creator. Do not edit, delete, or replace existing evidence.
2. Run the routine verifier. If it passes, preserve its output and do not promote any orphan.
3. If an orphan candidate is suspected, obtain its **exact existing object key** from the auditor-controlled log or storage inventory. Never guess a key.
4. Run `python -m tools.level3_staging.auditor_recovery_android '<exact-key>'`. This verifies the signature and byte-for-byte local/Drive agreement; it **never writes or advances the trusted latest pointer**.
5. Interpret:
   - `already_committed`: exact candidate equals trusted latest; no action.
   - `unanchored_candidate_manual_review`: latest pointer missing; **do not auto-promote**.
   - `candidate_requires_database_ancestry_review`: compare the independently verified prior anchor at its recorded sequence with Neon history before any new signed checkpoint.
   - `candidate_requires_manual_review`: reject unattended recovery.
   - Any exception: fail closed; preserve diagnostics without secrets.
6. Recovery promotion is deliberately **not implemented**. Escalate for independent review and a separate, tested recovery procedure.

## Security limitations and production acceptance gates

- **Google Drive is mutable**, even in a separate account. Rclone's list-then-upload is not atomic; concurrent writers may create duplicates. It does not satisfy WORM.
- Local POSIX files can be altered by a privileged device operator. The encrypted Android Ed25519 key is software-backed, not KMS/HSM.
- In-memory mirror acknowledgements are lost on process crash; recovery inspection intentionally cannot treat them as durable proof.
- A valid signature plus matching mirror cannot prove the database has not been rolled back unless a separately trusted prior anchor is retained and chain ancestry is checked.
- No production promotion until an independent append-only/object-lock retention service with restricted create-only credentials, retention policy, trusted head, and deletion-denial evidence is configured and tested.
- Additional required gates: physical Android kill/restart test, missing-evidence and replay drills, credential rotation and revocation verification, independent role-isolation review, monitoring/alerting, incident response, and approved production release.
- No live capital, live trading, or production custody operations permitted by these staging checks.
