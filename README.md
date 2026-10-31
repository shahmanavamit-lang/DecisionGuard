# DecisionGuard

Task authority before agent actions. Evidence for every intervention.

DecisionGuard aims to detect departures from authorized agent tasks, explain decisions, contain affected work, and check whether independent work can continue. **Phases one through eight are implemented in cumulative standalone folders.** Broader semantic-agent evaluation remains; this is not a production-readiness claim.

| Phase | What you can run |
| --- | --- |
| [Phase one](phase-one/README.md) | Original synthetic in-memory gateway |
| [Phase two](phase-two/README.md) | Local authority, approvals, revocation, durable execution and receipts |
| [Phase three](phase-three/README.md) | Vetted statistical profiles, triage evidence and reviewed holds |
| [Phase four](phase-four/README.md) | Managed dependencies, containment, delegation and checked continuation |
| [Phase five](phase-five/README.md) | Fixed local worker processes, brokered tools and bounded execution |
| [Phase six](phase-six/README.md) | Backend owner controls, investigation state, review-preview correction, and initial HTML/CSS/JavaScript console |
| [Phase seven](phase-seven/README.md) | Reproducible backend evaluation, honest comparative reports and output-integrity hardening |
| [Phase eight](phase-eight/README.md) | Offline source release, health checks, backup and safe recovery |

## Start DecisionGuard

Update your existing clone, then start the application from the repository root:

```sh
git pull origin main
python3 start.py
```

The browser interface opens automatically. Paste the one-use code printed in the terminal. Then choose a text file, review its permissions, and run the analysis—no JSON editing needed. The HTML/CSS/JavaScript UI is the normal application experience, not an optional add-on. Keep the terminal open while using the app.

Requires Python 3.11–3.14 on macOS/Linux or WSL. No pip packages, external APIs, API keys, or Node server. [First-run guide](phase-eight/README.md).

For a new clone:

```sh
git clone https://github.com/shahmanavamit-lang/DecisionGuard.git
cd DecisionGuard
python3 start.py
```

Each phase folder is cumulative. Earlier folders are historical snapshots and remain unchanged. Use `phase-eight` for the current application; do not combine source folders. Advanced CLI commands remain available for development and administration.

## Current boundary

The trusted local owner controls authority. Tools read imported file snapshots and write database-local notes. Statistical behavior evidence does not establish broad detector accuracy. Managed lineage supports containment; dispatch always checks current authority and dependencies. Workers are deterministic text processors, not LLMs, and their restrictions are not a general hostile-code sandbox. The web interface is local-owner tooling, not a public multi-user deployment.

[Review of phases 1–5](phase-six/docs/REVIEW_PHASES_1_TO_5.md) · [Phase-eight release](phase-eight/docs/RELEASE.md) · [Threat model](phase-eight/docs/THREAT_MODEL.md) · [MIT license](LICENSE)

GitHub is used for source publication and development CI, not as an application runtime dependency.

Latest maintenance review: [phases 1–7 checks and corrections](phase-seven/docs/REVIEW_PHASES_1_TO_7.md). Phase eight adds release/recovery tooling and the guided UI-first application.
