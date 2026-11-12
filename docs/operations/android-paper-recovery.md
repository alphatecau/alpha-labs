# Android paper journal verification and recovery

The historical operator journal is at ~/.alpha-labs-paper/alpha-paper.sqlite3 and the previously reported backup is at ~/alpha-labs-paper-backups/paper-backup-001.sqlite3. Their existence and current contents must be checked on the device. Quit the paper terminal before verification. Run these commands from a checked-out release candidate in Termux private storage.

## Read-only device verification

~~~sh
python -c 'import sqlite3,sys; print("Python",sys.version.split()[0],"SQLite",sqlite3.sqlite_version); raise SystemExit(sys.version_info < (3,12))' && PYTHONPATH=packages/alpha_lab/src python -m alpha_lab.research.local_paper_recovery verify --journal "$HOME/.alpha-labs-paper/alpha-paper.sqlite3" --backup "$HOME/alpha-labs-paper-backups/paper-backup-001.sqlite3" --minimum-events 2 && PYTHONPATH=packages/alpha_lab/src python scripts/local_paper_live_smoke.py
~~~

The recovery command takes read-only file snapshots and prints the canonical paths, owner binding, event counts, chain digests, replay results, cash, fees, positions and backup lineage. An exact fill-history match or valid prefix must be established. The two-fill floor catches the previously observed incorrect empty-path selection. A file with an active writer or SQLite sidecar requires a cleanly stopped snapshot. Offline valuation uses the last recorded simulated fills. An independent checkpoint comparison is reported as NOT TESTED unless separately held sequence and digest are supplied.

The opt-in live smoke uses three public Coinbase books and a disposable working journal. It prints source and receipt times and simulates a small buy and sell per pair when all books are fresh. The two historical files are outside its write paths. Retain detailed provider and journal output privately with the candidate Git SHA and device version. A quote failure reports simulated execution as NOT TESTED.

## Save a new backup of the stopped journal

Quit the paper terminal first. From the verified checkout, run the backup command with an unused filename in the existing Termux backup directory.

~~~sh
PYTHONPATH=packages/alpha_lab/src python -m alpha_lab.research.local_paper_recovery backup --journal "$HOME/.alpha-labs-paper/alpha-paper.sqlite3" --destination "$HOME/alpha-labs-paper-backups/paper-backup-002.sqlite3" --minimum-events 2
~~~

PASS reports the saved path, verified event count and `EXACT_FILL_HISTORY`. The command preserves existing files and publishes the verified copy without relying on hard links. Abrupt termination during publication can leave an empty reservation. Treat it as a failed backup and use a new filename.

## Prepare a working copy

A working copy requires the original and its independently checked backup. It writes only to a newly chosen directory. Schema changes occur on the temporary copy, followed by a verified halted startup before publication.

~~~sh
PYTHONPATH=packages/alpha_lab/src python -m alpha_lab.research.local_paper_recovery prepare-copy --journal "$HOME/.alpha-labs-paper/alpha-paper.sqlite3" --backup "$HOME/alpha-labs-paper-backups/paper-backup-001.sqlite3" --minimum-events 2 --destination "$HOME/.alpha-labs-paper-working"
~~~

Launch the verified copy after confirming the reported path and account. The terminal requires explicit --init to create a fresh account in a new directory.

~~~sh
PYTHONPATH=packages/alpha_lab/src python -m alpha_lab.research.local_paper_terminal --directory "$HOME/.alpha-labs-paper-working"
~~~

Use state for risk, source times, cash, positions, NAV, P&L, fees, recent fills and the last backup receipt in this session. If live valuation is unavailable, review the health flags and keep the runtime halted. Use new-id before a submission and retain the ID. Repeat the exact terms and ID after an uncertain response. Use backup with a new path in a separate existing Termux private directory. The tool publishes the backup only after structural and independent replay checks pass.

## Recover when the journal is damaged

Preserve both original files. Use an independently recorded event sequence and digest from the previously verified backup and restore into a new directory. A digest supplied by the same potentially replaced file does not establish independent rollback resistance.

~~~sh
PYTHONPATH=packages/alpha_lab/src python -m alpha_lab.research.local_paper_recovery restore-backup --backup "$HOME/alpha-labs-paper-backups/paper-backup-001.sqlite3" --destination "$HOME/.alpha-labs-paper-restored" --expected-sequence "$ALPHA_VERIFIED_SEQUENCE" --expected-head "$ALPHA_VERIFIED_HEAD"
~~~

Open only the restored path after checking the receipt. Confirm startup HALT and replayed balance, positions and count. A protected owner journal requires the original independent checkpoint authority. The local restore verifies the fill checkpoint scope, with control-state anti-rollback requiring protected custody.

A graphical Android interface is a future enhancement. The current operator surface is the tested terminal.
