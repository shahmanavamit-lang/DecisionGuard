# Phase three: local behavior profiles and explained review

A standalone cumulative DecisionGuard application. It retains phase two's durable authorization, immutable file snapshots, grants, revocation, budgets, receipts and local atomic execution, and adds **learned frequency/transition profiles from owner-approved local traces**.

No external APIs, API keys, hosted models, downloaded dependencies or hardcoded business records. Python 3.11+ standard library; Linux/macOS or Linux under WSL. The application trusts the local OS owner, not arbitrary code executing as that owner. Open this folder in VS Code. Use `python3` if `python` is unavailable.

```sh
python run.py --help
python -W error::ResourceWarning -m unittest discover -s tests -v
```

## Learning walkthrough using your files

Provide a UTF-8 input document and a UTF-8 note; choose a new private workspace:

```sh
python scripts/learning_walkthrough.py --input /path/to/input.txt --note /path/to/note.txt --workspace local/learning
```

This explicitly scripted exercise imports your data, labels the resource, runs eight controlled benign training tasks, freezes their traces, and trains a profile for a separate target task. A separate held-out benign trace is evaluated. An unusual authorized write is held before its effect, explained, then released by an explicit owner review. `report.json` contains actual persisted outcomes and dataset hashes. Eight repeated reads demonstrate mechanics, not model quality or resistance to attacks. No real AI agent is running here.

The earlier file-driven enforcement walkthrough is also available:

```sh
python scripts/walkthrough.py --input /path/to/input.txt --restricted /path/to/second.txt --note /path/to/note.txt --workspace local/enforcement
```

Both scripts create local databases containing supplied content. They refuse existing workspace directories. Do not upload generated databases, custom action files or private reports.

## Normal operation with your own traces

```sh
python run.py --db local/state.sqlite3 init
python run.py --db local/state.sqlite3 import-file input /path/to/input.txt
python run.py --db local/state.sqlite3 label input --version 1 --class document --impact 2
python run.py --db local/state.sqlite3 approve examples/scope.template.json --reason "Approve local review"
python run.py --db local/state.sqlite3 grant review-grant --principal local-worker --task local-review --ttl 3600
python run.py --db local/state.sqlite3 submit examples/read.template.json --principal local-worker
python run.py --db local/state.sqlite3 dispatch read-001 --principal local-worker
```

Templates are editable policy/action inputs, not bundled records. Resource versions and impact/class labels are owner-controlled. Labels cannot silently change: import a new resource version and approve its permissions to change its classification. Impact uses the operator's 1–5 assessment, from low-impact public activity to highly sensitive activity; the model never invents it.

Review completed tasks yourself before freezing them as benign traces. Choose the split before training. A trace snapshots completed receipt-backed steps in runtime event order, including resource class, operation and bytes; it excludes raw document and note content. A task can be frozen only once, so its source cannot be relabeled into another split. Do not treat an unfinished prefix as representative of a whole task. The owner is responsible for the benign judgment and appropriate task-family selection.

```sh
python run.py --db local/state.sqlite3 approve-trace benign-1 --task completed-task-1 --split train --reason "Inspected the complete benign run"
# Repeat for distinct, completed tasks to create benign-2, benign-3, etc.
python run.py --db local/state.sqlite3 train target-task --traces benign-1 benign-2 benign-3
python run.py --db local/state.sqlite3 evaluate target-task --traces heldout-1
```

The named tasks/traces in this example must exist. Create their scopes and grants through the same owner workflow. The target task must be distinct from all training tasks. At least three training traces are required; fewer than 20 is explicitly marked limited training, and 20 is not a statistical guarantee. Profiles bind to the target's current scope version. Training creates a new immutable profile version; live activity never updates it automatically.

Only `train` traces are eligible for fitting. Only `validation`/`test` traces are eligible for evaluation. Reserve held-out tasks before tuning; do not repeatedly tune against the test set. Evaluation reports total steps, flagged steps and hypothetical holds for owner-vetted benign runs. Those holds are false holds in that evaluation, not attack detections. The feature set may add little value beyond rules on some workloads; report that instead of asserting improved security.

## How decisions work

- Hard scope, grant, expiry, revocation, integrity and budget checks always win. A familiar pattern or owner behavior review cannot grant an otherwise forbidden action.
- A profile learns operation/resource-class frequencies, smoothed previous-to-next transition probabilities, and observed per-task action/byte maxima. Exact resource names do not become learned features.
- Signals identify an unseen action class, a transition probability below 0.15, or a cumulative count/volume above training maxima. Laplace smoothing uses one count per known action class plus one unknown class. Thresholds are an initial engineering heuristic, not calibrated security probabilities.
- Authorized reads and isolated novelty remain allowed and explained. Writes with two or more signals are held. Unlabeled writes or writes under a stale profile are held conservatively. No-profile cold start with known labels relies on hard scope and explicitly reports its lack of baseline.
- Held work remains queued internally with reason `behavior_review`; public results expose status `held`. Revocation can cancel it. No local effect or receipt is produced while held.

```sh
python run.py --db local/state.sqlite3 review REQUEST_ID --reason "Verified this particular proposed write"
python run.py --db local/state.sqlite3 dispatch REQUEST_ID --principal local-worker
python run.py --db local/state.sqlite3 reconcile REQUEST_ID
python run.py --db local/state.sqlite3 events
```

Review requires a current active profile and rechecks hard authority. It binds to the request, profile version and scope version. A new profile invalidates the old release; a scope/grant change still requires new authority. Unlabeled/stale-profile holds require labels/current training before release. Reviews do not train the baseline.

Every action result includes `behavior`: baseline status, sample count, profile version, training dataset hash, observed/expected signals, scope version, hard-policy reason, evidence severity and impact. Risk priority is severity × impact × 5: severity 0=no signal, 1=one novelty signal, 2=multiple signals, 3=hard-policy denial. Missing impact gives `null`, not an invented score. This is triage, not attack probability; a hold due to missing/stale data can have no statistical severity, and hard denial does not depend on the score.

## Storage and boundaries

Use a **new phase-three database** (schema version 2). Phase-two schema 1 is deliberately rejected, not silently upgraded. Keep its snapshot; reimport files and explicitly recreate authority for phase three. This phase does not provide an in-place database migration. All existing source folders remain unchanged.

Exit status: 0 for successful commands/queued/completed results, 3 for denied/cancelled/held, 2 for input/ownership/storage errors. Inspect the returned status and receipt. Completed request IDs return historical results without re-executing, even after authority changes. Logical principals are trusted-runner assignments, not independently authenticated OS accounts.

No autonomous LLM, semantic malware attribution, multi-agent containment, calibration claim, encrypted storage or hostile-code sandbox. Profile quality depends on appropriate, genuinely benign and varied traces. Counts and byte maxima are coarse; patience or permitted semantic misuse may evade them. Resource labels and policy correctness remain trusted assumptions.

[Learning design](docs/LEARNING.md) · [Storage architecture](docs/ARCHITECTURE.md) · [Threat model](docs/THREAT_MODEL.md) · [Phase report](docs/PHASE_REPORT.md) · [MIT license](LICENSE)
