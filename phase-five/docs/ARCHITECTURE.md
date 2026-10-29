# ADR 002: offline, transactional local execution

Date: 28 October 2026. Status: implemented for phase three.

## Updated constraints

The user requires local files and code, no external APIs or API keys, and no hardcoded business data. SQLite replaces the previously proposed PostgreSQL service. Python's standard library supplies the database driver; direct checkout execution requires no installation. These are established libraries, not custom replacements for a database engine or cryptographic implementation. The application logic is implemented in this repository.

Business records are imported from operator-provided text files. Scope JSON and action JSON are explicit inputs. No test fixture is automatically loaded into a live database. Logical identifiers, validation limits and supported operation names in code are protocol definitions, not business records.

## Data and authority

- `resources`: immutable versioned UTF-8 snapshots, digest and byte size.
- `tasks`: current approved scope version and cumulative action/byte usage.
- `scopes`: immutable approved policy versions, owner UID, reason and time.
- `grants`: logical principal, task, scope version, expiry and revocation state.
- `actions`: durable canonical request, principal-bound fingerprint and state.
- `notes`: local write effects, uniquely keyed by request ID.
- `receipts`: unique completion evidence for each executed action.
- `events`: ordered audit records without copied file/note bodies.

The initial schema migration is applied transactionally on explicit initialization and recorded using `PRAGMA user_version=2`. Opening a missing file never silently creates a new store. An unsupported schema version is rejected without migration or downgrade. Phase one's in-memory state has no persistent schema to migrate.

## Execution and serialization

```text
User files -> owner imports immutable versions
Scope JSON -> owner approval -> version-bound grant
Action JSON + trusted runner identity -> durable submit
Queued action -> BEGIN IMMEDIATE -> fresh grant/scope/budget checks
    denied -> denial event -> commit
    allowed -> local read/note + budget charge + receipt + completion event -> commit
```

Each operation opens and closes its own SQLite connection. `BEGIN IMMEDIATE` serializes authority mutations and dispatch. SQLite foreign keys are enabled, and synchronous mode is FULL. The bounded lock timeout yields a storage error rather than bypassing checks. Effects are confined to the same database transaction: there is no arbitrary file write, remote send or external callback whose effect could escape a rollback.

A dispatch that acquires the write transaction first can commit before revocation. Revocation then cancels remaining queued requests. A revocation that commits first prevents later dispatch. Grant expiry is checked inside the dispatch transaction; it is an authorization-at-dispatch boundary, not a guarantee to retract a result after the clock passes expiry. Budgets are charged atomically once per completed request across all grants for the task.

## Durable idempotency and reconciliation

The action fingerprint binds canonical request content and logical principal to the request ID. A retry with the same fingerprint returns the existing record. Conflicting reuse is rejected. Completed, denied and cancelled states are terminal. This preserves historical evidence when authority changes; it never re-executes a completed request. Returning stored output is an owner-level historical lookup, not a fresh worker authorization service.

Before commit, a process crash rolls back both the note and its evidence. After commit, a lost client response is resolved by reading the stored state and receipt. A storage/commit error does not claim success or absence of effects; the caller must reconcile when the database is available. Exactly-once local note effects are supported by a unique key and transaction, not by a claim about arbitrary external systems.

## Evidence and limitations

Scope and grant changes have audit events. Request validation failures are CLI diagnostics before domain submission. Read receipts identify the snapshot digest and version. Hashes detect accidental payload inconsistency but are not proof against an owner who can modify both data and hashes. Audit records are application-append-only, not tamper-proof against the database owner.

Local worker names are assigned by the trusted runner. Same-UID hostile code, malicious administrators, network filesystems and distributed authority are outside the boundary. Learning and review are described in LEARNING.md. Selective continuation remains future work.

Phase-three schema 2 adds immutable labels, curated traces, versioned profiles, assessments and request reviews. It intentionally rejects older databases; initialize a fresh store. See LEARNING.md for behavioral dispatch and hold semantics.

Phase-four addendum: these inherited notes describe the foundation. See CONTAINMENT.md for schema 3, managed contexts, output delivery, containment and continuation; phase four requires a fresh database.

Phase-five addendum: fixed worker process integration, broker authority and run recovery are described in WORKERS.md. Schema 4 requires a fresh store. Inherited notes describe earlier foundations; no arbitrary hostile-code sandbox is claimed.
