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
| [Phase six](phase-six/README.md) | Backend owner controls, investigation state, review-preview correction, and optional custom console |
| [Phase seven](phase-seven/README.md) | Reproducible backend evaluation, honest comparative reports and output-integrity hardening |
| [Phase eight](phase-eight/README.md) | Offline source release, health checks, backup and safe recovery |

## Continue with phase eight

If already cloned, update from your repository directory:

```sh
git pull origin main
cd phase-eight
python3 run.py --help
python3 -W error::ResourceWarning -m unittest discover -s tests -v
```

For a new clone:

```sh
git clone https://github.com/shahmanavamit-lang/DecisionGuard.git
cd DecisionGuard/phase-eight
```

Python 3.11+ on Linux/macOS or Linux under WSL. No runtime package installation, external API, API key, or cloud account is required. Follow the [file-driven walkthrough](phase-eight/README.md#start) with your own input. The database starts empty; synthetic fixtures are only in historical phase one and explicitly labeled tests/exercises.

**Backend/CLI development remains primary.** Phase six's custom HTML/CSS/JavaScript console is saved for later use; no Streamlit or Node runtime is used. It opens only when you explicitly run `console` and is not required for subsequent development.

Each folder is a cumulative project. Use the latest phase for current work; do not combine their source directories. Earlier folders are historical snapshots; current fixes are in phase eight. They remain unchanged for comparison, and CI checks phases independently. Schema 4 stores from phase five are compatible with phases six through eight; no database is automatically copied or migrated.

## Current boundary

The trusted local owner controls authority. Tools read imported file snapshots and write database-local notes. Statistical behavior evidence does not establish broad detector accuracy. Managed lineage supports containment; dispatch always checks current authority and dependencies. Workers are deterministic text processors, not LLMs, and their restrictions are not a general hostile-code sandbox. The optional web console is local-owner tooling, not a public multi-user deployment.

[Review of phases 1–5](phase-six/docs/REVIEW_PHASES_1_TO_5.md) · [Phase-eight release](phase-eight/docs/RELEASE.md) · [Threat model](phase-eight/docs/THREAT_MODEL.md) · [MIT license](LICENSE)

GitHub is used for source publication and development CI, not as an application runtime dependency.

Latest maintenance review: [phases 1–7 checks and corrections](phase-seven/docs/REVIEW_PHASES_1_TO_7.md). Phase eight adds the release and recovery tooling.
