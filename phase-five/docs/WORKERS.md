# ADR 005: fixed local worker with a parent authority broker

Date: 29 October 2026. Phase five follows the user's offline requirement. It uses an explicit local rule-based worker rather than inventing a claim to have trained a foundation model or adding an external model service.

The parent loads owner configuration and binds a context to its stored grant/task/principal. It persists a run record before starting the child. The child receives only the validated plan and permitted tool results; it proposes resource operations over bounded JSON-line pipes. The parent checks the proposal against the plan, constructs the authoritative Action and invokes the existing engine. No worker credential or database path exists in the protocol.

The fixed worker computes data-dependent text statistics. It does not parse document instructions, evaluate code, select arbitrary executables or load plugins. A `receive` proposal is delivered through checked context consumption, preserving lineage. Cold-start/active-profile decisions, holds and containment remain in the engine rather than in worker logic.

Process defense in depth: isolated/no-site Python, environment stripping, closed unrelated descriptors, private empty working directory, deadline-bound pipe I/O, bounded frames/steps and POSIX resource limits. The worker imports its trusted standard library before installing audit restrictions on file/network/process operations. These hooks are not a kernel security boundary and arbitrary hostile code is not supported. Linux has a 512 MiB address-space cap; macOS is explicitly different.

Only one run may be active for a context. All prior completed context history remains conservatively linked, even though a new process has fresh Python memory. Run/action identifier collisions are rejected, avoiding accidental replay of historical results into a new worker. Terminal runs are never automatically replayed. Output buffers and audit diagnostics omit raw data except for approved tool delivery and owner views.

On a worker error or deadline, the parent terminates and reaps its process group and records failure. The engine's already committed receipts remain authoritative. If the broker dies, a durable running record is not guessed to be completed or failed; owner stop contains the context and prevents further authorized effects. A live stopped worker may remain until its next exchange/deadline. Each subsequent operation still rechecks authority in the engine transaction, so stop/containment and effects have the same serialization cutoff as phase four.

Schema 4 adds worker_runs. A fresh database is required; old snapshots are preserved rather than migrated silently. Public source contains no business input. Templates define editable control flow; test data is temporary. Development CI uses GitHub, but the application itself makes no network calls.
