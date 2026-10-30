# Phase-six threat model

## Protected property

Within the trusted local runner, actions can execute only with a current matching grant, approved scope, exact operation/resource/version permission, intact resource snapshot and sufficient task budget. Caller-controlled action data cannot grant authority. Denied actions produce no local tool effect or execution receipt.

## Trusted boundary

The local POSIX OS account, Python runtime, SQLite, application code, database storage and owner administration are trusted. The database's UID must match the current process; group/other file permissions are rejected. Private working directories are recommended. The owner is inherently able to inspect or change the database and run application code.

A principal name is a logical identity selected by a trusted runner, not a credential. This CLI is owner tooling, not a service for untrusted OS users. A hostile process under the same UID can invoke administrative functions or change the database; the application does not claim to prevent that.

## Untrusted inputs

File contents and proposed actions can contain forged approval instructions, unknown fields, invalid paths, resource choices, stale grant IDs or repeated request IDs. The parser restricts request structure. Approval state is modified only by explicit owner operations; text in imported data is never interpreted as permission.

## Tested controls

Exact operation/resource/version matching; principal and task binding; expiry; stale scope rejection; queue cancellation; latest authority at dispatch; transactional cumulative budgets; durable idempotency; missing/corrupt/unavailable evidence storage; schema mismatch; immutable snapshots; and rollback on failure or process termination during a local write.

## Remaining limits

No general hostile-code sandbox, independent worker authentication, encryption at rest, signed ledger, semantic intent detection or malware identification. Managed contexts do implement narrowing delegation and a dependency graph; these trust the owner runner to capture provenance. Same-scope harmful use can still occur. Approval quality depends on the operator. UID changes when copying databases between machines require an explicit migration design; do not silently rewrite owner records.

File import is a privileged administrative action: it may read any source file available to the owner. Worker actions can name only imported resource IDs and versions, not arbitrary filesystem paths. Output and `inspect`/`reconcile` are owner views and can contain sensitive data. Avoid sharing database files or command output publicly.

SQLite transactions cover database-local effects only. Remote APIs and arbitrary source-file mutation are not supported, so the project does not imply their atomicity. OS/filesystem failures may leave storage unavailable; no success is invented during such failures.

Phase-four addendum: these inherited notes describe the foundation. See CONTAINMENT.md for schema 3, managed contexts, output delivery, containment and continuation; phase four requires a fresh database.

Phase-five addendum: fixed worker process integration, broker authority and run recovery are described in WORKERS.md. Schema 4 requires a fresh store. Inherited notes describe earlier foundations; no arbitrary hostile-code sandbox is claimed.


## Phase-six addendum

Backend owner controls and the optional console are described in [CONSOLE.md](CONSOLE.md) and [ADR 006](ADR-006-owner-controls-and-optional-console.md). CLI use remains primary. This snapshot retains schema 4 and fixes reviewed-hold continuation previews; it does not add general hostile-code isolation or production assurance.
