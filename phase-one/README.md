# Phase one: foundation and first enforced action

This phase implements the first vertical slice of DecisionGuard: authenticate a demonstration identity, check its trusted task grant, authorize an exact operation/resource pair, and execute a synthetic tool only after an allow decision.

## Quick start

Requirements: Python 3.11+. No pip install is required.

```sh
python run.py demo
python -m unittest discover -s tests -v
```

Use `python3` on macOS/Linux if necessary, or `py -3` on Windows. These commands run from this folder. Optional isolation: `python -m venv .venv`, then select `.venv` as your interpreter in VS Code. The project also runs without a virtual environment because it has no external runtime packages.

The JSON demonstration shows:

- `mode`: `deterministic_simulation`.
- A quotation read with decision `allow`, scope version `1`, and a completed receipt.
- An HR read with decision `deny`, reason `outside_scope`, no output and no receipt.
- `backend_receipt_count`: `1`; `hr_read_count`: `0`.

Event and receipt identifiers/timestamps differ between runs. Both actions use the same valid identity. The backend supports HR reads, but the procurement task grant does not. A fake approval sentence in the quotation is treated as content and never updates authority. Requests are scripted; no model is interpreting the quotation in this phase.

## Check individual actions

```sh
python run.py check examples/allowed.json
python run.py check examples/denied.json
```

Exit status `0` means success, `3` means policy denial, and `2` means invalid input or command usage. The denied example intentionally returns a nonzero status. Each CLI invocation starts a fresh in-memory runtime. For a sequence sharing state, use the Python API or `demo`.

Accepted action fields are exactly `request_id`, `task_id`, `grant_id`, `operation`, and `resource_id`. Identity comes from the separate credential lookup, not an identity field supplied in the action. Extra fields, duplicate JSON keys, invalid identifiers and files over 16 KiB are rejected. The CLI uses a public demonstration credential internally; it is not a secure login service.

## Python API

For scripts launched from this folder, add `src` to the import path as below. An optional `python -m pip install -e .` makes the package and `decisionguard` command available in a virtual environment; that installation may download setuptools. Direct checkout execution stays offline.

```python
import sys
sys.path.insert(0, "src")
from decisionguard.contracts import ActionRequest
from decisionguard.demo import DEMO_CREDENTIAL, build_demo

gateway = build_demo()
result = gateway.execute(
    ActionRequest("my-request", "procurement-001", "quotation-grant", "read", "quotation:acme"),
    credential=DEMO_CREDENTIAL,
)
print(result.decision.outcome)
print(gateway.events)
print(gateway.receipts)
```

There is no HTTP service in phase one. The reusable API is the Python `Gateway.execute` method.

## Layout

```text
src/decisionguard/contracts.py  Immutable contracts and strict action parsing
src/decisionguard/policy.py     Pure authorization function
src/decisionguard/runtime.py    Synthetic backend, gateway and in-memory evidence
src/decisionguard/demo.py       Trusted demo configuration and paired scenario
src/decisionguard/cli.py        JSON command-line interface
examples/                      Allowed and denied input files
tests/                         Contract, enforcement and subprocess CLI tests
docs/                          Design, threat model and phase report
```

## Boundaries

State disappears when the process exits. Request IDs are rejected on reuse within one runtime, but this is not durable idempotency. The runtime is single-threaded and has no concurrency, expiry/revocation service, dynamic approval endpoint, database, learned detector, risk score, agent framework, network isolation or dashboard. Trusted application code can call synthetic tools directly; this is not a sandbox for hostile Python code. Backend exceptions propagate with an `unknown` event, without asserting that effects were prevented.

The phase-one claim is deliberately narrow: within this controlled call path, denied requests do not invoke the backend. Phase two will address durable authority and execution correctness when requested.

[Architecture](docs/ARCHITECTURE.md) · [Threat model](docs/THREAT_MODEL.md) · [Phase report](docs/PHASE_REPORT.md) · [License](LICENSE)
