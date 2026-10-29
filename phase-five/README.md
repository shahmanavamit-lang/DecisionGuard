# Phase five: local workers behind an authority broker

A cumulative DecisionGuard application with **real local worker processes** connected to the phase-four managed runtime. A fixed deterministic worker reads approved text and computes character, word, line, UTF-8 byte counts and SHA-256, then proposes a local note. All tool execution stays in the parent broker behind current permission, learning, budget and containment checks.

No external API, API key, hosted model, runtime package download or seeded business records. This is a rule-based file worker, **not an LLM, semantic summarizer or general autonomous planner**. It treats document text as data and never executes instructions found inside it.

## Start

Python 3.11+ on Linux/macOS or Linux under WSL. Open this folder in VS Code; `python` may be used instead of `python3` where configured.

```sh
python3 run.py --help
python3 -W error::ResourceWarning -m unittest discover -s tests -v
python3 scripts/worker_walkthrough.py --input /path/to/document.txt --workspace local/workers
```

Use a new workspace directory. The walkthrough imports your UTF-8 file, creates explicit owner authority, starts two worker processes and saves `report.json`. The first produces actual content-derived statistics. The second proposes an outside-task read that is denied and contained. The report is derived from real execution receipts; it is not an LLM injection benchmark. Source files remain unchanged; notes live in SQLite.

Earlier learning and containment walkthroughs remain in `scripts/`. Previous phase folders are unchanged. **Phase five requires a fresh schema-4 database**; older stores are rejected without mutation. Reimport local inputs and recreate owner approvals rather than silently upgrading old authority.

## Configure your own managed worker

The inherited commands remain available: `init`, `import-file`, `label`, `approve`, `manage`, `grant`, and `context`. The phase-four guide explains managed setup. A complete minimal example:

```sh
python3 run.py --db local/state.sqlite3 init
python3 run.py --db local/state.sqlite3 import-file input /path/to/document.txt
python3 run.py --db local/state.sqlite3 label input --version 1 --class document --impact 2
python3 run.py --db local/state.sqlite3 approve examples/scope.template.json --reason "Approve local analysis"
python3 run.py --db local/state.sqlite3 manage local-review
python3 run.py --db local/state.sqlite3 grant review-grant --principal local-worker --task local-review --ttl 3600
python3 run.py --db local/state.sqlite3 context local-context --grant review-grant --memory local-memory
python3 run.py --db local/state.sqlite3 run-worker local-context run-001 examples/worker-plan.json
python3 run.py --db local/state.sqlite3 worker-status run-001
python3 run.py --db local/state.sqlite3 note run-001.1
```

Adjust the scope template's limits to your input and summary size. The plan names resources already imported and authorized; it does not grant permission. The worker receives neither the database path nor grant/principal/task IDs. The broker derives authority from the registered context and stamps request IDs as `RUN_ID.STEP_INDEX`.

## Plan format and tools

```json
{
  "steps": [
    {"kind": "read", "resource_id": "input", "resource_version": 1},
    {"kind": "summarize", "resource_id": "input", "resource_version": 1, "source": 0}
  ]
}
```

- `read` proposes a `read_file` action over a versioned imported snapshot.
- `summarize` computes deterministic statistics from a preceding read/receive result and proposes `write_note`. Its `source` is a prior step index. The source data remains in the context's dependency history even if the note's destination resource is different.
- `receive` uses `{"kind":"receive","output_id":"ANOTHER_COMPLETED_REQUEST"}`. The broker delivers it only through phase-four `consume`, recording dependencies and checking the recipient's authority/budget. Only text-bearing outputs can feed this worker.

There is no arbitrary Python, shell, plugin, network endpoint, filesystem path or credential field in the plan. Unsupported fields fail validation. Worker proposals must match the configured step order, operation and resource. A compromised proposal cannot replace task, grant or identity fields. Actual note content remains untrusted worker output; it is not a new approval source.

`note` is an owner forensic command that retrieves a completed local note. It may reveal data and must not be exposed as a worker endpoint. Worker outputs exchanged between contexts must still use `receive`/`consume`, not owner diagnostics.

## Process separation and limits

Each run launches the repository's fixed worker using isolated Python (`-I -S`), an empty inherited environment, closed unrelated file descriptors and a new empty working directory. Only bounded JSON frames pass over stdin/stdout. No database handle, file paths or credentials are sent to the worker.

The worker installs audit restrictions that reject file opens, sockets, shell/process execution and selected filesystem operations after its trusted imports. It has no user-code execution facility. Tests directly probe blocked file, socket and shell operations in the real worker executable.

Limits: 1–100 plan steps; 8 MiB protocol frames; default 10-second communication deadline, configurable with `--timeout` up to 60 seconds; CPU limit rounded up from the deadline; no core dumps or regular-file writes; descriptor limit 32. Linux additionally caps process address space at 512 MiB. macOS does not get that address-space cap. Database lock timeouts and parent cleanup can extend elapsed wall time beyond the communication deadline.

**This is not a kernel sandbox for arbitrary hostile Python code.** Audit restrictions protect the supported fixed worker; they do not justify executing untrusted plugins. Same-UID owner code can bypass the application. The parent broker is trusted and holds authority. Stronger isolation for arbitrary third-party agents would need a separate OS/container design and evaluation.

## Holds, cancellation and recovery

A denied, cancelled or held action stops the worker before its next step. A behavior hold creates no note effect; owner review remains separate. Completing/releasing that action manually does not automatically resume the stopped process. Use a deliberate new run with current authority and account for any effects already completed.

```sh
python3 run.py --db local/state.sqlite3 worker-status run-001
python3 run.py --db local/state.sqlite3 reconcile run-001.0
python3 run.py --db local/state.sqlite3 stop-worker run-001 --reason "Owner stops or recovers an interrupted run"
```

Run IDs are one-use, including failed runs. The broker rejects collisions with preexisting action IDs and concurrent runs on the same context. After a broker crash, the durable state may still say `running`; it is **not** automatically assumed dead or replayed. The owner can stop it, which contains its context, revokes dependent authority and records `stopped`. An active worker exits on its next exchange or deadline; this command does not promise an instantaneous OS kill. Restart work in a genuinely fresh context with newly approved authority.

The broker kills/reaps its process group on timeout or normal teardown. A response lost after a tool commit does not erase the receipt. `worker-status` shows run progress; `reconcile` is authoritative for a particular action. If storage is unavailable, do not infer success or non-execution.

CLI exit codes: 0 for successful commands/completed runs, 3 for blocked/stopped runs or policy holds/denials, 2 for failures/invalid input. Read the JSON state as well as the exit code.

## Scope and next work

Local file snapshots, database notes, deterministic worker computation, checked output delivery, durable run records and bounded process lifecycle are implemented. No hosted-model integration, API key configuration, semantic reasoning or autonomous browser access. Detector quality, broad adversarial robustness and high-throughput performance remain unproven. Next phase, only when requested: an operator console over the actual persisted state.

[Worker design](docs/WORKERS.md) · [Phase report](docs/PHASE_REPORT.md) · [Threat model](docs/THREAT_MODEL.md) · [MIT license](LICENSE)
