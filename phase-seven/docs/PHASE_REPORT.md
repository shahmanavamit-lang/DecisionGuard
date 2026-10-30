# Phase-seven completion report

30 October 2026. Backend evaluation and adversarial hardening; optional UI unchanged.

Delivered a seeded, manifest-driven, offline synthetic matrix: 160 executions over eight families and four internal configurations. Reports contain denominators, per-case outcomes, actual effect receipts, intervention sequence positions, source hashes, environment, timing, CPU, peak process RSS, storage and zero model calls. Full local evidence is reproducible; compact results and a generated comparison table are included in `evals/`.

135 cumulative tests passed after the maintenance review (124 inherited plus eleven evaluation/integrity checks). These include existing rollback/crash, revocation races, replay, delegation, missing lineage, broker timeout and post-commit lost-response tests. The full matrix passed its frozen bounded safety/continuation gates. JavaScript assets remain unchanged from phase six; no UI work is required to use this phase.

Confirmed hardening: stored output delivery now checks receipt-backed payload integrity and missing provenance before consumption. Inconsistent evidence contains the task without delivering or charging the invalid handoff. Schema 4 is retained; earlier snapshots are preserved unchanged.

Findings: selective containment preserved 10/10 eligible independent steps versus 0/10 for whole-task pause in these replay families. Both allowed 5/20 evaluator-declared harmful reads when actual authority was deliberately too broad. Selective clean-task utility was 10/15 due to legitimate novelty holds. These limitations are not hidden by the passing explicit-scope gates. The project does not yet establish local semantic-agent security, broad detector accuracy or production readiness.

AgentDojo was considered but no valid model-based external comparison is feasible with the current deterministic workers. No external score or adapter is claimed. See EVALUATION.md for exact mode differences, exclusions, metric definitions, held-out setup and reproducibility limitations.

Remaining planned phase: release engineering and operational readiness, only upon user authorization. A real local reasoning agent remains a separate unresolved scope/hardware decision. Backend/CLI stays primary; the saved custom interface remains optional.

Maintenance review: [REVIEW_PHASES_1_TO_7.md](REVIEW_PHASES_1_TO_7.md) records additional handoff consistency, intervention reporting, manifest validation, and documentation fixes. The 160-case matrix was regenerated; effect/utility aggregates stayed unchanged. Phase eight remains unstarted.
