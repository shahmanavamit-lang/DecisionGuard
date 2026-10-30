# ADR 004: managed versioned lineage and conservative containment

Date: 29 October 2026. Schema 3 adds managed tasks, contexts, versioned nodes, edges, delegated restrictions and output data. Execution is still local and transactional.

A context has one grant, a declared memory compartment, a current revision and quarantine state. Every managed resource read advances the context, linking the immutable imported resource node and prior context snapshot. The resulting output depends on that snapshot. Output delivery checks recipient authority and advances the receiving context with an incoming dependency. Shared-memory contexts gain reciprocal edges. Delegation creates a permission-narrowed grant and links parent state to the child's initial state.

Managed authorization requires a registered clean context, live ancestor grants, child permission restrictions and clean transitive dependencies. Grant creation without a context does not bypass enrollment. Dependencies originate in runtime operations, not action JSON or self-reported influence lists. Logical memory compartment assignment is still a trusted runner responsibility.

Containment starts with all snapshots of the affected context. Forward graph traversal identifies consumers, and each newly affected context adds all its snapshots. Delegated grants are revoked transitively, including children without contexts. Shared-memory cycles terminate using visited sets. Unknown lineage includes every context on the same task before graph expansion. Queued affected requests are cancelled within the same transaction. Existing completed effects remain recorded.

The algorithm is conservative: historical clean outputs may be quarantined when their source context later fails. It aims for justified independent continuation, not mathematically minimal containment. Independent contexts using the same immutable input resource do not depend on one another merely because they read that resource; there is no backward propagation from a context to an input resource.

Continuation checks are point-in-time evidence. Dispatch repeats authority and dependency checks under the SQLite write transaction and records checked ancestors/revision/scope before effects commit. Graph updates, local effects, usage charges, receipts and events commit together. A crash before commit rolls them back together. A containment transaction serialized before dispatch prevents effects; work committed before containment remains historical.

Unmanaged tasks provide backward-compatible phase-three behavior but cannot request continuation evidence. Owner forensic reads remain available and must not be used as worker message transport. The runtime is not safe against its own OS owner rewriting storage or bypassing adapters. Graph scale and recovery from trusted backups remain future evaluation/operations work.

Phase-five addendum: fixed worker process integration, broker authority and run recovery are described in WORKERS.md. Schema 4 requires a fresh store. Inherited notes describe earlier foundations; no arbitrary hostile-code sandbox is claimed.
