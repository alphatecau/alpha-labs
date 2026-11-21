# GitHub-mediated Level 3: Android staging acceptance

Status: **development only**. No direct MCP write tool is enabled. Existing Level 2 tunnel and adapter remain unchanged.

## Design and trust boundary

- The operator reviews a GitHub pull request, identifies an immutable **full 40-character commit SHA**, and independently verifies the expected SHA-256 of the exact file.
- An operator-run Termux CLI fetches the pinned file from GitHub, checks its digest and allowlisted relative path, and requires an explicit confirmation word.
- Creation is exclusive (never overwrite). Updating requires both expected old and new SHA-256 and rechecks the target before replacement.
- Both commands are limited to `docs/level3-staging/[A-Za-z0-9_-]+.md` and `tests/level3-staging/[A-Za-z0-9_-]+.txt`, at most 32 KiB.
- GitHub PR approval **is not independently verified by these scripts**. A full commit SHA and content digest alone do not prove human review. The operator must check them outside the untrusted worker.
- A compromised process under the same Android UID can potentially tamper with staging files, the installer, or local confirmations. These scripts do **not** establish independent security isolation.
- No arbitrary shell commands, trading operations, GitHub token access or production writes are provided.

## Android acceptance (operator's existing third Termux session only)

1. Keep the existing first and second Termux sessions running.
2. Fetch these three files from a reviewed **pinned commit**, into `~/termux-level3-source/tools/level3_staging` and `~/termux-level3-source/tests` respectively:
   - `tools/level3_staging/github_pinned_install.py`
   - `tools/level3_staging/github_pinned_update.py`
   - `tests/test_level3_github_pinned_install.py`
   - `tests/test_level3_github_pinned_update.py`
3. Run `python -m unittest discover -s tests -p 'test_level3_github_pinned_*.py' -v`. Expected: **14 tests**. This is an expectation, not an observed result.
4. Verify Level 2 adapter is still listening on `127.0.0.1:8765` and all three existing read tools work.
5. For real create/update, independently inspect the target file in the reviewed GitHub commit, verify the content SHA-256, and run the CLI with `--commit`, `--path`, `--sha256` for create, or `--old-sha256` and `--new-sha256` for update.
6. Do not use the current installer to update code or any non-staging workspace. Do not enable direct MCP write tools.

## Remaining before operational acceptance

- Run tests on actual Android and perform one approved create and one approved update with verified hashes.
- Add durable append-only audit/reconciliation and a rollback/recovery procedure.
- Confirm GitHub review status using a separate trusted channel; verify commit identity, not just branch names.
- Design independently held approval credentials before any direct MCP write exposure.
