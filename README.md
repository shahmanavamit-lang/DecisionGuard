# DecisionGuard

Task authority before agent actions. Evidence for every intervention.

DecisionGuard is being developed in independently runnable phase folders. The long-term goal is identity-drift detection, explained containment, and verified continuation for autonomous agents. **Only phase one is implemented.**

| Phase | Status | What you can run |
| --- | --- | --- |
| [Phase one](phase-one/README.md) | Implemented | Typed task authority, synthetic tools, allow/deny decisions, events, receipts and tests |
| Later phases | Not started | Durable execution, learning, multi-agent containment, integrations, operator console and evaluation |

## Run phase one

Install Python 3.11 or newer, then:

```sh
git clone https://github.com/shahmanavamit-lang/DecisionGuard.git
cd DecisionGuard/phase-one
python run.py demo
python -m unittest discover -s tests -v
```

On macOS/Linux, use `python3` if `python` is unavailable. On Windows, `py -3` also works. No API key, cloud account, third-party runtime library, or database is needed.

Open `phase-one` in VS Code and select a Python 3.11+ interpreter. You can also download the repository ZIP and open that folder.

## How phase folders work

Each completed phase is published as a self-contained snapshot (`phase-one`, then `phase-two`, and so on). A later phase will include the cumulative runnable project, its own setup instructions, requirements and license; earlier snapshots remain available. Run one phase at a time. Do not combine package folders or install different snapshots into the same virtual environment. Root GitHub Actions checks the supported snapshots.

## Scope and evidence

The demo is deterministic and uses synthetic data. It demonstrates task-scoped enforcement despite a valid demo identity; it does not run an LLM or demonstrate learned drift detection, production authentication, or multi-agent containment yet. Read the [threat model](phase-one/docs/THREAT_MODEL.md) and [phase report](phase-one/docs/PHASE_REPORT.md).

Project code is provided under the [MIT license](LICENSE). Third-party development tools retain their own licenses; see [dependency notes](phase-one/docs/DEPENDENCIES.md).
