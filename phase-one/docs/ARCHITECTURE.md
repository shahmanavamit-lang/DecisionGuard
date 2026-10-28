# Architecture decision 001: small, inspectable enforcement core

Status: implemented for phase one. Date: 28 October 2026.

## Decision

Use Python 3.11+ immutable dataclasses, a pure policy function, and a synchronous in-memory gateway. Start with a CLI and a Python API. Keep HTTP transport and PostgreSQL for phase two, where durable execution warrants them. This intentionally refines the earlier proposed FastAPI stack without changing the underlying contracts.

```text
Proposed action JSON -> strict validation -> separate credential lookup
    -> trusted grant + current task scope -> policy decision
        deny -> event, no backend invocation
        allow -> synthetic backend -> receipt + event + returned output
```

The trusted configuration defines a task scope and a principal-bound grant for that scope version. A request names a grant but cannot create one. Policy checks authentication, grant existence, principal binding, task binding, current scope availability, scope version, exact operation/resource membership, and registered backend support. Default behavior is denial whenever a required check fails.

Permissions are pairs rather than independent operation and resource lists: permission to read one resource plus write another does not imply permission to read both. Grant scope does not depend on quotation text or proposed extra authority fields.

## Contracts

| Contract | Purpose |
| --- | --- |
| TaskScope | Trusted task ID, version, description and immutable permissions |
| Grant | Trusted principal-to-task binding and scope version |
| ActionRequest | Untrusted proposed operation and resource, with correlation IDs |
| Decision | Allow/deny, stable reason code, explanation, identity and scope version |
| Event | Request, decision, UTC timestamp, execution status and optional receipt link |
| Receipt | Evidence of a completed synthetic backend operation |
| ExecutionResult | Decision/event/receipt plus authorized tool output |

The gateway copies configuration maps on startup. Public evidence access returns tuples of frozen records. Raw credentials and tool output are excluded from the event ledger, although the local CLI deliberately prints authorized synthetic output in its result. Backend exceptions produce an unknown execution-status event and propagate to the trusted caller.

## Tradeoffs

Standard-library-only execution makes a fresh checkout simple and keeps policy independent of a provider or framework. In-memory state is not durable or independently tamper-proof. Python private attributes are a convention, not a security boundary. Concurrent use is unsupported. Duplicate request rejection only avoids accidental sequential reuse in one process.

Future adapters must pass through the same enforcement boundary. No continuation or learned behavior claim follows from this first policy core.
