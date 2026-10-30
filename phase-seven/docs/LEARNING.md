# ADR 003: explicit local statistical learning

Date: 29 October 2026. No external service or model is used.

The owner freezes reviewed benign execution traces into train/validation/test partitions. Traces originate from completion events joined to receipts, not self-reported agent reasoning. Training snapshots exclude payload content and exact resource IDs. Resource classes and impacts are immutable owner labels per imported resource version. Profiles are versioned per target task and bound to its scope version; cross-task role-level automation is deferred.

A profile stores operation/class frequency counts, transition counts, maximum task action count and maximum task bytes. Probability for a next token is `(transition_count + 1) / (outgoing_count + known_token_count + 1)`. A final category represents unknown actions. This is a sequence frequency estimate, not a probability that an agent is compromised. Profile source IDs, individual hashes and combined dataset hash are retained. Stored hashes detect accidental inconsistency; they cannot defend against the database owner changing both content and hashes.

Assessment runs during submission for evidence and again during dispatch on the current completed history. Failed or held attempts do not become completed behavioral history. Repeated request IDs do not add steps or consume budgets. Multiple workers' completed actions for the same task share sequence and cumulative totals; this is not a dependency graph or independent worker behavioral model.

Multiple novelty signals hold an authorized write. An explicit owner review can release this exact request only for the same current profile and scope versions. Dispatch still checks current grant, expiry, revocation, scope, integrity and budget. Cold start with trusted labels remains scope-governed and reports uncertainty. Missing labels/stale profiles hold writes rather than inventing a learned normal pattern.

Sample adequacy: three traces is a mechanical minimum, not enough to establish real-world reliability. Counts below 20 are labeled limited training; larger counts do not automatically establish representativeness. Isolated novelty is not proof of maliciousness. Several signals can be correlated, so the triage rubric is deliberately not a calibrated probability.

Held-out evaluation scores each step using only its preceding history, keeping fitting and evaluation separate. It reports raw denominators, flagged actions and hypothetical false holds on owner-approved benign data. No attack success rate or superiority claim is established. Maintain fresh unseen tasks for final testing and do not tune repeatedly to the test partition.

Initial deployment should use diverse local traces reviewed by the owner. If observed false holds outweigh useful signal or behavior adds nothing beyond hard rules, revise the model using validation data and report the limitation. Never silently learn from an unreviewed live run.

Phase-four addendum: these inherited notes describe the foundation. See CONTAINMENT.md for schema 3, managed contexts, output delivery, containment and continuation; phase four requires a fresh database.

Phase-five addendum: fixed worker process integration, broker authority and run recovery are described in WORKERS.md. Schema 4 requires a fresh store. Inherited notes describe earlier foundations; no arbitrary hostile-code sandbox is claimed.
