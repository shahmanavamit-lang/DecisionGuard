# Maintenance review: phases one through seven

30 October 2026. Scope: verify and correct the existing project only. Phase eight was not started. Backend-first and offline constraints remain unchanged.

## Verification

| Phase | Passing tests | Role |
| --- | ---: | --- |
| One | 26 | Historical synthetic gateway |
| Two | 43 | Durable authority and local effects |
| Three | 59 | Statistical profiles and review holds |
| Four | 83 | Managed containment and continuation |
| Five | 103 | Real fixed worker processes |
| Six | 124 | CLI owner controls and optional console |
| Seven | 135 | Current cumulative backend, evaluation and integrity corrections |

All original suites were rerun successfully. Additional regressions first reproduced failures, then passed with the corrections below. The current suite, JavaScript syntax check, and full 160-case evaluation passed. Aggregate harmful-effect, task-utility, benign-intervention and independent-work results were unchanged; intervention sequence reporting and source hashes were regenerated. Tests are cumulative, so their sum must not be presented as a count of distinct mechanisms or independent security experiments.

## Confirmed issues corrected in phase seven

1. A handoff could deliver output despite its source action having an inconsistent non-completed status. Require a completed source and matching source request ID before delivery.
2. Python equality allowed a boolean output version to compare equal to integer version 1. Require the version's actual type to be integer.
3. Malformed stored source proposals were parsed outside the integrity failure handler. They now enter conservative containment instead of raising an uncaught decoding error. Invalid handoffs neither deliver data nor increase usage budgets.
4. Evaluation first-intervention reporting omitted denials made at submission. Include the recorded denied submission, rather than incorrectly returning no intervention in rules-only cases.
5. Evaluation configuration could omit/duplicate families or modes without strict validation, and the declared dependent-work threshold was ignored. Require the complete known matrix, validate typed configuration, and use the declared threshold.
6. Root README's phase-seven row was separated from its table; current links/schema wording and threat-model heading were stale. Corrected these and clarified which snapshot contains current fixes.

Earlier phase folders remain historical snapshots, including their documented limitations and behavior later corrected in phases six/seven. Use phase seven for current work. The review does not imply that every historical version contains the latest fixes.

## Alignment with the aim

The system still enforces approved task authority, derives behavioral evidence from vetted traces, explains interventions, and checks dependency-based continuation. Input text does not grant authority; genuine owner changes use separate controls. Effects are established by receipts, not merely by attempted actions. No external model/API/key is required, no business dataset is silently seeded, and the optional UI remains unnecessary for the backend workflow.

Limits remain explicit: fixed deterministic workers are not semantic AI agents; broad real permissions can permit harmful use; benign novelty can be held; same-UID owner code is trusted; integrity checks do not create a tamper-proof ledger. This review supports the stated bounded prototype behavior, not a guarantee of perfection, zero remaining defects or production readiness. Broader semantic-agent evaluation and release engineering are not silently included in this maintenance task.
