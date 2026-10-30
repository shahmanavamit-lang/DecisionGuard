# Phase eight: release engineering

30 October 2026. Cumulative offline v1; prior phase folders unchanged. Schema 4 retained.

- 141 cumulative tests, including backup/restore authority, committed WAL preservation and reproducible archive checks.
- Full 160-case evaluation passed all declared gates. Generated results and source hashes refreshed.
- Optional UI JavaScript syntax check passed; browser behavior is unchanged from phase six.
- Real worker demo over the public README completed analysis and contained an outside-task request. See DEMO_RECORDING.json for its recorded command and results (text recording, not a video).
- Backup and restore drill passed health checks; restored grants revoked, contexts quarantined, queued work cancelled, running records stopped, receipts retained.
- Source archive extraction and clean-venv test run verify operation without installed packages. Explicit release file list, license and private-data scan cover the published snapshot.

See RELEASE.md for commands, architecture, Python integration, security reporting and recovery limits. Retention is an operator procedure over whole closed stores, not automatic deletion. No telemetry export, silent schema migration, hosted reasoning model or production-readiness claim. Optional packaging metadata remains developer-only; the supported source archive build uses Python standard library alone.
