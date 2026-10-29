# Phase four: managed dependencies, containment and continuation

This cumulative local application adds a managed runtime on top of phase three's policy, learning and durable SQLite execution. It records versioned context snapshots, resource reads, outputs, message consumption and delegation. It can quarantine affected work and let independently checked work continue.

**No external APIs, API keys, hosted models or preloaded business records.** Python 3.11+ standard library, Linux/macOS/WSL and a trusted local OS owner. The runner and logical context/memory assignments are trusted; this is not an OS sandbox or a live LLM integration.

## Run in VS Code

Update your existing clone with `git pull origin main`, then open `phase-four`:

```sh
python3 run.py --help
python3 -W error::ResourceWarning -m unittest discover -s tests -v
python3 scripts/containment_walkthrough.py --input /path/to/your/document.txt --workspace local/containment
```

Use a new workspace directory. The walkthrough runs two controlled scenarios using your file: an independent inventory branch continues after a supplier violates scope; a branch that consumed supplier output is cancelled. It writes a report from actual events and receipts. Scripted actions exercise the security runtime, not a real AI model's susceptibility to injection.

The earlier local-learning and enforcement walkthroughs remain available as `scripts/learning_walkthrough.py` and `scripts/walkthrough.py`. They run in compatibility mode without containment enrollment. For their usage, see [the phase-three guide](../phase-three/README.md), also summarized in [learning design](docs/LEARNING.md).

## Set up managed work

Initialize a **fresh schema-3 database**. Old databases are rejected without mutation; no automatic upgrade is supplied. Import your file, label it, approve an editable scope template, then enroll the task **before submitting any actions**:

```sh
python3 run.py --db local/state.sqlite3 init
python3 run.py --db local/state.sqlite3 import-file input /path/to/document.txt
python3 run.py --db local/state.sqlite3 label input --version 1 --class document --impact 2
python3 run.py --db local/state.sqlite3 approve examples/scope.template.json --reason "Approve local review"
python3 run.py --db local/state.sqlite3 manage local-review
python3 run.py --db local/state.sqlite3 grant review-grant --principal local-worker --task local-review --ttl 3600
python3 run.py --db local/state.sqlite3 context worker-context --grant review-grant --memory isolated-worker-memory
python3 run.py --db local/state.sqlite3 submit examples/read.template.json --principal local-worker
python3 run.py --db local/state.sqlite3 continuation read-001
python3 run.py --db local/state.sqlite3 dispatch read-001 --principal local-worker
python3 run.py --db local/state.sqlite3 graph
```

The owner assigns memory IDs to actual logical memory compartments. Reusing a memory ID declares shared state and intentionally couples containment. A new name does not physically isolate hostile code. Once a task is managed, every grant needs a registered context to execute. New grants cannot silently bypass that requirement. Existing action history cannot be retroactively declared clean through enrollment.

## Outputs, messages and delegation

A completed managed action produces an output node named by its request ID. The trusted runner must deliver outputs through `consume`; never copy raw payloads between contexts behind its back:

```sh
python3 run.py --db local/state.sqlite3 consume RECEIVING_CONTEXT COMPLETED_REQUEST_ID
```

Consumption checks recipient authority to read the originating resource, checks its current limits, and records the input dependency before returning data. Each consumption counts toward the task's action/byte budgets and behavior history. It is a new data delivery, not an idempotent action retry. It does not confer the sender's grant. Missing output provenance pauses the recipient's entire managed task; quarantined outputs are not delivered.

Owner-managed delegation creates a narrower grant on the same task (and therefore the same aggregate budget):

```sh
python3 run.py --db local/state.sqlite3 delegate PARENT_GRANT CHILD_GRANT --principal child-worker --permissions /path/to/permissions.json --ttl 300
python3 run.py --db local/state.sqlite3 context child-context --grant CHILD_GRANT --memory isolated-child-memory
```

Permissions JSON is an array of exact `{ "operation", "resource_id", "resource_version" }` records. Every permission must fit live parent authority. Expiry cannot exceed the parent's. Children can redelegate only within their own restrictions. Opening a child context records its dependency on the parent snapshot; ancestor authority is rechecked at dispatch. A message alone creates no delegation.

## Containment and verified continuation

Managed out-of-scope and delegated-scope violations automatically quarantine the offending context, forward consumers, shared-memory peers and affected delegated grants. The original operation remains denied. A mismatched logical principal cannot trigger quarantine of another context through a forged request. Behavioral novelty alone still follows phase three's review policy rather than being declared confirmed compromise.

```sh
python3 run.py --db local/state.sqlite3 contain CONTEXT --reason "Owner-confirmed incident"
python3 run.py --db local/state.sqlite3 contain CONTEXT --reason "Unknown shared state" --unknown-lineage
python3 run.py --db local/state.sqlite3 continuation REQUEST_ID
```

Containment revokes affected grants and cancels queued work atomically. Revoking a managed grant also contains its context and consumers. No automatic unquarantine exists. An independent branch can run only with clean recorded ancestors and current authority. `continuation` returns evidence, not a reusable execution permit. Dispatch rechecks dependencies, permission versions, expiry, revocation, budgets and behavioral holds in one transaction. Successful managed dispatch records a continuation event with checked nodes, context revision, memory ID and scope version.

Context snapshots advance on reads and consumption. Outputs retain their source context. Containment conservatively treats **all historical snapshots of an affected context** as affected, then traces forward; it may over-pause work that was actually clean. It never promises mathematically minimal isolation or knowledge of hidden model influence. Shared-memory cycles are traversed with visited sets. Unknown lineage expands containment rather than declaring independence.

## Compatibility, limits and evidence

Unenrolled tasks retain phase-three behavior and are **not protected by dependency containment**. They cannot claim a continuation decision. Use managed mode for phase-four workflows. `inspect` and `reconcile` remain owner forensic interfaces and can return historical quarantined content; they are not worker message-delivery APIs.

Local context state is logical and recorded by this runner. The runtime does not intercept arbitrary Python reads, clipboard transfers or code running as the owner. Scope quality, resource labels, actual memory separation and complete use of the runner remain trusted assumptions. No external tools, LLM, physical process isolation, encrypted ledger or production security guarantee.

A transaction committed before containment remains historical; containment cannot undo earlier disclosure. Snapshot copying and restoring old databases may resurrect old state and require separate recovery controls. The graph is durable but not tamper-proof against its owner. Maximum graph size/performance is not yet benchmarked.

All previous phase folders are preserved. [Review of phases 1–3](docs/REVIEW_PHASES_1_TO_3.md) · [Architecture](docs/CONTAINMENT.md) · [Phase report](docs/PHASE_REPORT.md) · [MIT license](LICENSE)
