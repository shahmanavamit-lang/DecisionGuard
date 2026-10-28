# DecisionGuard

Task authority before agent actions. Evidence for every intervention.

DecisionGuard is developed in independently runnable phase folders. The goal is identity-drift detection, explained containment, and verified continuation for autonomous agents. **Phases one and two are implemented; later phases have not started.**

| Phase | What you can run |
| --- | --- |
| [Phase one](phase-one/README.md) | Original synthetic, in-memory gateway demonstration |
| [Phase two](phase-two/README.md) | Offline file-backed authority, approvals, revocation, durable execution, receipts and tests |

## Start with phase two

Python 3.11+, on Linux/macOS or Linux under WSL:

```sh
git clone https://github.com/shahmanavamit-lang/DecisionGuard.git
cd DecisionGuard/phase-two
python run.py --help
python -W error::ResourceWarning -m unittest discover -s tests -v
```

Use `python3` where necessary. Open `phase-two` in VS Code. No pip installation, external API, API key or cloud account is needed to run the checkout.

The database starts empty. Follow the [file-driven walkthrough](phase-two/README.md#walkthrough-using-your-files) with your own input files. No business records are hardcoded or automatically loaded in phase two. Phase one's original synthetic fixtures remain only in its historical snapshot.

## Phase folders

Each completed phase is published as a cumulative standalone project. Use the latest phase for current work; previous folders remain runnable for comparison. Run each folder with its own interpreter environment if installing it. Do not merge their package directories. CI checks each phase independently.

## Current boundary

Phase two trusts the local OS owner and runner. It stores local file snapshots and database-local notes, and never calls a hosted model or remote tool API. It does not yet learn behavioral drift or perform multi-agent containment. Read the [threat model](phase-two/docs/THREAT_MODEL.md) and [phase report](phase-two/docs/PHASE_REPORT.md).

Source code is [MIT-licensed](LICENSE). Each standalone phase contains its own license and dependency notes. GitHub is used for source publication and development CI, not as a runtime dependency.
