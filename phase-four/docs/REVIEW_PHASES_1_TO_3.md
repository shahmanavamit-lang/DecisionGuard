# Review of phases one through three

Reviewed 29 October 2026 before phase-four delivery. Scope: local source, design contracts, tests and integration direction. No claim of an independent security audit or exhaustive proof.

## Direction confirmed within the documented boundary

Phase one separates proposed actions from trusted scope and gates synthetic effects. Phase two makes authority, budgets, effects and receipts transactional and durable, with idempotency and dispatch-time rechecks. Phase three adds owner-curated statistical evidence without letting a model score override hard permission rules. These foundations match the original identity-drift brief and can support selective containment. The project remains fully local per the user's revised constraint.

Review focused on authentication/authority claims, permission pairing, revocation ordering, transaction rollback, duplicate execution, profile provenance, training/test partitioning and review release. Regression tests are retained and rerun from clean snapshots; they do not establish general adversarial robustness.

## Finding corrected in the cumulative phase-four implementation

Phase three accepted the resource class string `unlabeled`, but trace curation treats that string as a reserved missing-label sentinel. An operator could therefore create a valid-looking label whose traces could never train. Phase four rejects the reserved class with an explicit error; a regression test covers it. Historical phase-three source remains unchanged as requested.

## Important constraints, not missing guarantees to conceal

- Logical principal names are supplied by a trusted runner. Same-UID hostile code can invoke owner operations. No phase currently supplies an OS sandbox or independent worker identity service.
- Phase three's short repeated-read walkthrough proves mechanics only. Learned signal usefulness, false-positive rates on varied tasks and adaptive-attack resistance remain unproven. No success percentage or superiority claim is warranted.
- Database versions are explicit but phase-three and phase-four builds require fresh stores. There is no production migration/restore system yet.
- Hard policy and data classification can be wrong even when enforcement is correct. Local owner data access remains privileged.
- New phase-four workflows must be enrolled before action execution. Compatibility-mode tasks preserve earlier behavior and must not be described as containment-protected.

These constraints do not justify abandoning the design. They define the next implementation and evaluation boundaries. Phase four addresses observable dependencies and containment, while live agent integration, stronger isolation and broad evaluation remain future phases.
