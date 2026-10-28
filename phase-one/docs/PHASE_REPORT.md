# Phase-one completion report

Date: 28 October 2026. Scope: foundation and first enforced action only.

## Delivered

Typed immutable contracts; explicit task/grant policy; synthetic quotation and HR backend; gateway execution gate; UTC events and execution receipts; CLI and Python API; allowed/denied examples; requirements and package metadata; MIT license; architecture and threat model; GitHub Actions test matrix.

## Validation

Local Python 3.14.6: 26 unittest tests pass. Coverage includes allowed effects, denial before backend invocation, forged approval text, authentication and grant binding, task mismatch, missing authority, stale versions, operation/resource pairing, unsupported tools, duplicate sequential requests, unknown backend outcome, credential/payload omission from events, immutable configuration, malformed inputs, and CLI exit codes.

Commands:

```sh
python -m unittest discover -s tests -v
python run.py demo
```

Demonstration outcome: one completed quotation-read receipt; zero HR-read receipts; the HR request is denied despite the same valid demo identity. Tests use backend spies and receipt assertions, not only the gateway's explanation.

The CI workflow is configured for Python 3.11, 3.12, 3.13 and 3.14. Local success does not itself establish that remote CI has completed; GitHub Actions provides that status.

## Limits and handoff

This is a deterministic simulation, not a real-agent benchmark. Authority and evidence are in memory; concurrency and durable execution are not implemented. Learning, scoring, delegated-agent containment and the UI remain later phases.

Next phase when requested: durable authority, persistence, approvals, revocation and execution correctness. Preserve this folder as the phase-one snapshot; develop the next cumulative project in `phase-two` and use a separate virtual environment.
