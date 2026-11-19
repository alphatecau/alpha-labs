# Level 3 staging: exact execution evidence — 19 November 2026

## Scope and verdict

**PASS:** Real Neon PostgreSQL reservation state transition, real Google Drive upload and raw download, matching SHA-256 and byte-for-byte comparison. **PASS:** CI automated PostgreSQL + in-memory Drive adapter end-to-end tests. **NOT PROVEN:** One unattended automated service using production credentials, strict owner-token-bound completion in the *live* manual sequence, or an independently held Ed25519 signing key and externally persisted signed audit checkpoint. Production release remains NO-GO.

## CI execution

- Commit: `647502be8a57b6352ee5d6ab65dd88e7f5cac443`.
- Workflow: https://github.com/alphatecau/alpha-labs/actions/runs/44476584175
- PostgreSQL integration job ID `135398499027`, conclusion **success**.
- Job log at 2026-11-19 07:03:12 UTC: `test_corrupt_readback_keeps_reservation_pending ... ok`, `test_reserve_upload_readback_commit_and_duplicate_denial ... ok`, `Ran 2 tests in 0.084s`, `OK`.
- Other PostgreSQL reservation tests: `test_exclusive_claim_and_completion ... ok`, `test_separate_connections_compete_for_unique_key ... ok`; `Ran 3 tests in 0.090s`, `OK`.
- All seven workflow conclusions success. The CI Drive adapter is synthetic and does not use real Google OAuth.

## Real staging sequence

- Neon project `frosty-river-38771873`, branch `br-solitary-hall-a7h0lefq`, database `level3custody`, table `level3_custody.drive_upload_reservation`.
- Auditor Drive folder `118pwq_VOAGeeS1NOTXmoA4ZVEx4AcMo6`, auditor account `alpha.tec.au869@gmail.com`.
- Source native Google Doc ID `1cmFxjxesnmN-oO8Lq8UPeFwBcmFqCZkhtGNNjjkXy18`; exported as `text/plain`, 90 bytes.
- Source SHA-256 `8cd3e10c2c610e0981c63ab57f90366401e69486dab607ca3cfaeb132e4692b1`.
- **07:06:06.467 UTC:** INSERT into isolated Neon `drive_upload_reservation`, with parent ID, SHA-256, generated 32-hex owner token and state `reserved`. One row returned.
- **After reservation:** real Google Drive `upload_file` consumed an exported connector `file_uri` and returned `success=true`, Drive ID `1Dauu533wTklxUPV_Z0zMgWYbpdRn944x`, matching content-addressed filename, correct parent folder. https://drive.google.com/file/d/1Dauu533wTklxUPV_Z0zMgWYbpdRn944x/view
- Real Drive `fetch(download_raw_file=true,include_base64=false)` returned file reference and `file_size_bytes=90`, correct parent and file ID.
- Local `sha256sum` of source and downloaded file: both `8cd3e10c2c610e0981c63ab57f90366401e69486dab607ca3cfaeb132e4692b1`; `cmp -s` returned exit code **0**.
- **07:06:31.313 UTC:** Neon UPDATE returned `state=verified`, `file_id=1Dauu533wTklxUPV_Z0zMgWYbpdRn944x`, `verified_at=2026-11-19T07:06:31.313Z`, one row.

## Security limitations requiring separate acceptance

1. Live UPDATE filtered by parent, SHA, state and owner-token **format**, but not exact generated owner-token value. This is a manual integration exercise, not proof of the application helper's exact token-ownership enforcement. The disposable PostgreSQL CI test does check wrong-owner denial.
2. The live sequence was manually orchestrated with connected tools; it did not execute `reserved_upload_and_verify` as one deployed service against real Google Drive.
3. No independently controlled Ed25519 signing key was used to sign a checkpoint persisted in an auditor-controlled append-only store; existing `external_anchor.py` signature tests are offline.
4. Google Drive folder append-only guarantees, immutable checkpoint continuity, Render-to-Neon TLS, tenant isolation, Android acceptance and operator release approval are still open.

**Do not mark Level 3 production ready or enable live trading from this evidence.**
