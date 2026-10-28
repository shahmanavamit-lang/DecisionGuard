# Phase-one threat model

## Protected property

A proposed tool action entering the configured gateway must match the authenticated principal's trusted grant and current task scope before the synthetic backend executes it.

## Trusted components

Startup configuration, credential mapping, Python process, policy implementation, gateway, synthetic backend and operator. Resource identifiers and permissions originate in this configuration. The public demo credential is only a reproducible fixture.

## Untrusted inputs

Action JSON, resource/operation choices, grant/task identifiers supplied by the requester, and supplier quotation text. The requester may try to name another grant, forge approval fields, request unrelated HR access, or use malformed input. External text is never an approval source.

## Enforced cases

- A valid procurement identity requesting HR access is denied before tool execution.
- A different identity cannot borrow the procurement grant.
- Unknown grants/tasks and stale scope versions fail closed.
- Unsupported actions cannot run even if mistakenly listed in a scope.
- Request JSON cannot provide identity, permissions or an approval override.
- A synthetic quotation containing an approval claim cannot alter trusted configuration.

## Outside this phase

No defense against hostile code inside the process, administrator modification, stolen real credentials, network bypass, denial of service, concurrent races, distributed execution, or malicious content that remains inside all permitted actions. No inference of malicious intent, causal attribution, calibrated risk, learning, or selective containment. No real identity provider, token lifecycle, database, external tools or real HR data.

Malformed requests are rejected before becoming domain events; parser errors are CLI diagnostics. Backend failure may leave an uncertain effect, so the runtime records unknown rather than claiming a denial. Production deployments will need protected audit storage, trusted administration, credential separation and runtime isolation in later phases.
