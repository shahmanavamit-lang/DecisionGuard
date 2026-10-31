# DecisionGuard

**Keep automated work within the limits you approve—and understand what happened.**

DecisionGuard checks a worker’s requests before allowing them, records completed actions, and stops affected work when necessary. Its HTML/CSS/JavaScript interface is the normal application experience, included at startup—not an optional add-on. No Streamlit, external APIs, API keys or hosted models.

## Start the application

Requires Python 3.11–3.14 on macOS, Linux, or WSL using its Linux filesystem. No pip installation is needed.

From this folder:

```sh
python3 start.py
```

Your browser opens automatically. Paste the **one-use access code printed in the terminal**, then keep that terminal open while using the app. This local code protects your workspace; it is not an API key. Press Ctrl+C in the terminal to stop. If a browser does not open, use the printed address. If the port is busy, run `python3 start.py --port 0`.

The first start creates an empty, private workspace at `phase-eight/local/state.sqlite3`; subsequent starts reopen it. Existing databases are never overwritten. To open a different store, use `python3 start.py --db /path/to/state.sqlite3`. Earlier phase databases are not selected automatically. `python3 run.py` with no arguments also starts the interface; explicit CLI commands remain available for advanced work.

## Your first run—no JSON required

1. **Choose a file.** Select a non-empty UTF-8 text file up to 200 KB, such as `.txt` or `.md`. PDF and Word documents are not supported by this guided flow.
2. **Review its limits.** Give the task a name and approve two actions: read that file and save its text statistics inside the workspace. The screen shows the usage limit. Your original stays unchanged; no other file is authorized.
3. **Run approved analysis.** See the actual word, line and character counts, along with whether each action completed or was blocked.
4. **Open Results.** Revisit saved results and expand evidence only when you need it. Refresh retrieves the latest recorded state.

No sample business data is preloaded. The guided worker computes statistics; it does not generate an AI-written summary. The first run has no trained behavior profile. Explicit permission checks still apply. Advanced controls retain custom plans, owner review, permission editing, containment and recovery; they are outside the beginner’s path.

## Understand the outcome

| What you see | What it means |
| --- | --- |
| Completed | The action ran and has an execution receipt. |
| Blocked | The requested step was refused; inspect its reason. Earlier steps may have completed. |
| Needs review | The action is waiting for an owner decision. |
| Isolated | Affected working sessions cannot continue under their old authority. |
| In progress | The stored run has not recorded completion; refresh or inspect recovery controls. |

A successful first analysis demonstrates controlled execution. It is not a malicious-input benchmark. The [evaluation report](evals/RESULTS.md) compares explicit scope violations, shared dependencies and other labeled synthetic cases. Broad genuine permissions can still allow harmful use; benign novelty can be held.

## If something interrupts your work

If setup fails or a response is lost, **refresh and inspect the recorded task/result before starting again**. Setup consists of separately recorded import, label, approval and enrollment steps; a partial setup does not grant worker access. The UI never automatically retries a run. After reloading the page, an approved but unused guided task can be started from Approved work. Previously used run IDs cannot be replayed.

The workspace and uploaded content remain on this computer. The UI binds only to `127.0.0.1` and uses a local session and request checks. It is intended for the trusted local owner, not public hosting or multiple remote users. Fixed workers are not general AI agents or a sandbox for arbitrary hostile code. This is a bounded prototype, not a production-security guarantee.

## Guides and verification

- [User interface and recovery](docs/CONSOLE.md)
- [Release, backup, restore and operations](docs/RELEASE.md)
- [Advanced CLI guide](docs/CLI_GUIDE.md)
- [Threat model](docs/THREAT_MODEL.md) · [Security reporting](SECURITY.md) · [MIT license](LICENSE)

```sh
python3 -W error::ResourceWarning -m unittest discover -s tests -v
python3 evals/run.py --output local/evaluation
```

Use a new evaluation output directory. These commands run tests and labeled synthetic evaluations; they do not populate your normal workspace. Schema 4 remains compatible with phases five–seven. Earlier phase folders are historical snapshots; use this cumulative phase for current work.
