# Phase two: durable local authority and execution

DecisionGuard now stores task approvals, grants, pending actions, local effects, receipts and audit events in a local SQLite file. It starts empty and operates on **your imported UTF-8 files**. No external API, API key, hosted model, network client, seeded business records or third-party runtime package is required.

This is the cumulative phase-two application. Phase one remains unchanged as a historical snapshot. Learning and multi-agent containment are not implemented yet.

## Requirements

- Python 3.11+ with the standard-library `sqlite3` module.
- Linux or macOS; on Windows use Python inside WSL. Native Windows is not supported in this phase because ownership checks use POSIX UIDs and file modes.
- A local disk owned by your OS account. Shared/network filesystems are outside the tested scope.

Open this folder in VS Code and select your Python interpreter. Use `python3` instead of `python` where needed. No `pip install` is necessary. Optional isolation: `python -m venv .venv` and select its interpreter.

```sh
python run.py --help
python -W error::ResourceWarning -m unittest discover -s tests -v
```

## Walkthrough using your files

Prepare three UTF-8 text files: an input document, a second document used for the restricted-access exercise, and a note you want to store. Choose files appropriate for a local development exercise. The script imports their contents into a private database; it does not upload them.

```sh
python scripts/walkthrough.py --input /path/to/input.txt --restricted /path/to/second.txt --note /path/to/note.txt --workspace local/walkthrough
```

Use a new workspace path each time; the script never overwrites an existing workspace. It generates scope/action JSON, a database, and a report from actual execution. It demonstrates:

1. An authorized read of the imported input.
2. A denied read of the second file before owner approval.
3. A note stored once, with a retry returning the existing result after restart.
4. A new owner-approved scope and grant allowing the second file.
5. Revocation cancelling an otherwise eligible queued read.

The report should contain three receipts, one stored note, and action states `completed`, `denied`, `completed`, `completed`, `cancelled`. These are checked by the walkthrough test; the report itself is assembled from database outcomes. Document text is never parsed as an approval. The script is a deterministic exercise of enforcement, not an AI agent.

## Manual workflow

Start with your own database and import a file:

```sh
python run.py --db local/state.sqlite3 init
python run.py --db local/state.sqlite3 import-file input /path/to/input.txt
```

Initialization creates no users, grants, tasks or business resources. Import returns a resource version, byte count and SHA-256. Each import creates an immutable snapshot in the database: changing the original file does not silently alter an approved resource. Reimporting creates another version that needs explicit permission.

Copy and edit `examples/scope.template.json` for the resource ID/version you imported. Set budgets for your task; the template values are examples, not hidden defaults. Then:

```sh
python run.py --db local/state.sqlite3 approve examples/scope.template.json --reason "Approve my local file review"
python run.py --db local/state.sqlite3 grant review-grant --principal local-worker --task local-review --ttl 3600
python run.py --db local/state.sqlite3 submit examples/read.template.json --principal local-worker
python run.py --db local/state.sqlite3 dispatch read-001 --principal local-worker
python run.py --db local/state.sqlite3 reconcile read-001
python run.py --db local/state.sqlite3 inspect
python run.py --db local/state.sqlite3 events
```

`submit` durably queues an eligible request without reading the protected resource or creating a note effect. `dispatch` checks current authority and budgets again before execution. `reconcile` only looks up the result; it never retries an effect. `inspect` is an owner command and includes stored outputs. `events` omits resource and note bodies, but still includes identifiers and operator-provided approval reasons.

To store a local note, use an action with `operation: "write_note"` and a nonempty `content` string. The scope must authorize that exact operation, resource ID and version. The note is stored in SQLite, not appended to your source file. It returns a note ID and digest; receipts prove the local effect. Actions do not accept paths or approval fields.

## Approval changes and revocation

Editing JSON alone changes nothing. Run `approve` as the database's OS owner to create a new scope version. Older grants become stale; issue a new grant ID to use the updated scope. Usage counters belong to the task and are not reset by scope updates or additional workers.

```sh
python run.py --db local/state.sqlite3 revoke review-grant
```

Revocation cancels queued requests using the grant. Expired grants are also denied at dispatch. An action that committed before revocation is retained as a historical completed result; revocation cannot retract a read already returned. Repeating its ID returns the receipt without executing again. Use a new request ID for a new attempt under changed authority.

## Identity and trust boundary

The OS owner controls administration and the trusted runner. `--principal` names a logical worker selected by that runner; it is **not a separate authenticated user account**. The database must belong to the current UID and exclude group/other permissions. This phase prevents forged authority inside action data, but is not a sandbox against hostile code running as the same OS user. Do not expose the CLI or Python engine as a public server.

## Status and failures

CLI exit codes: `0` for completed commands/queued or completed results, `3` for policy denial or cancellation, `2` for input, ownership or storage errors. Check both the status and receipt, not just process exit `0`. A `not_found` reconciliation is a lookup result, not proof of a completed effect.

Request IDs are durable idempotency keys. Reusing the same ID with identical content/principal returns the existing state; different content/principal is rejected. Denied/cancelled IDs remain terminal. Effects, budget charges, receipts and completion events share one SQLite transaction. On a lost response, run `reconcile`; do not assume failure means no effect. A failed or unavailable database never authorizes an action through a fallback.

## Layout and limits

`src/decisionguard/` contains strict contracts, the schema/transaction layer, owner administration, dispatch and CLI. `tests/` covers real SQLite transactions, concurrency, process crashes and subprocess commands. `scripts/walkthrough.py` accepts user files. `docs/` explains design and limitations.

Resources and action content are bounded to 1 MiB. Data is local and not encrypted by this app. Database access and owner command output can reveal imported content. No remote tools, keys, token service, learned anomaly detector, risk score, agent framework, dashboard or delegated context graph is implemented. GitHub is used only to distribute code and run development checks, not as an application dependency.

[Architecture](docs/ARCHITECTURE.md) · [Threat model](docs/THREAT_MODEL.md) · [Operations](docs/OPERATIONS.md) · [Phase report](docs/PHASE_REPORT.md) · [License](LICENSE)
