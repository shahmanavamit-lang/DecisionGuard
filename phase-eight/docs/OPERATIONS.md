# Local operations and schema

Use a private local folder. Initialization creates the database with mode 0600 and new directories with mode 0700. Existing parent-directory permissions are not silently changed. The database is rejected if it is a symlink, belongs to another UID, or is readable/writable by group or others. SQLite journal files inherit the database's restrictive permissions.

Run `python run.py --db local/state.sqlite3 init` exactly once per new store. It refuses existing paths. Initial tables and `user_version=4` are committed together. Normal opens use `mode=rw` so a missing database cannot be replaced by an empty one. Future versions must introduce explicit migration logic; unsupported versions currently fail closed.

Every import is a snapshot. To use updated file content, import again, approve the new resource version, and issue a new grant. Historical snapshots and receipts remain available. Task budgets count all completed reads/notes over the task's lifetime; retries with the same ID do not count twice, but a new ID represents a new operation and does count. New grants or scope versions do not erase prior usage.

Use `reconcile REQUEST_ID` after a lost response. `completed` plus its receipt means the recorded local transaction committed. `queued` means no committed effect exists in the current authoritative database and it remains eligible for fresh dispatch checks. `denied` and `cancelled` are terminal. `not_found` is not a completed operation. If the database cannot be read, the outcome remains unknown to the caller.

Phase eight adds `scripts/operations.py` health, backup and locked restore. Follow [the release runbook](RELEASE.md) for recovery and whole-workspace retention; never prune live evidence rows.

The public repository excludes local databases, journals and `phase-eight/local/`. Request JSON can contain note text, so keep custom requests in the ignored local folder. `inspect` and `reconcile` are owner diagnostics and may print imported text. Audit events exclude payload bodies, but approval reasons and identifiers can still be sensitive.

Native Windows is intentionally unsupported until a trustworthy Windows owner/access-control adapter exists. Use WSL on its Linux filesystem for this phase.

Phase-four addendum: these inherited notes describe the foundation. See CONTAINMENT.md for schema 3, managed contexts, output delivery, containment and continuation; phase four requires a fresh database.

Phase-five addendum: fixed worker process integration, broker authority and run recovery are described in WORKERS.md. Schema 4 requires a fresh store. Inherited notes describe earlier foundations; no arbitrary hostile-code sandbox is claimed.


## Current phase-six workflow

Schema 4 from phase five is directly compatible. CLI remains primary; use `overview`, `start-fresh-worker`, and `approve --expected-version` for the new owner controls. The optional `console` command is the only listener entry point and must remain loopback-only. See [CONSOLE.md](CONSOLE.md) for session and lost-response recovery.
