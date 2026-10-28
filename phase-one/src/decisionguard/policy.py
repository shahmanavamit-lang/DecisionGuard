"""Pure, deterministic authorization. Does not execute tools or read model text."""
from .contracts import ActionRequest, Decision, Grant, Outcome, Permission, Reason, TaskScope


def evaluate(
    request: ActionRequest,
    principal_id: str | None,
    grant: Grant | None,
    scope: TaskScope | None,
    supported: frozenset[Permission],
) -> Decision:
    version = scope.version if scope else None

    def deny(reason: Reason, explanation: str) -> Decision:
        return Decision(Outcome.DENY, reason, explanation, principal_id, version)

    if principal_id is None:
        return deny(Reason.AUTHENTICATION_REQUIRED, "A valid demo credential is required.")
    if grant is None:
        return deny(Reason.UNKNOWN_GRANT, "No trusted grant exists for this request.")
    if grant.principal_id != principal_id:
        return deny(Reason.PRINCIPAL_MISMATCH, "This grant belongs to a different identity.")
    if grant.task_id != request.task_id:
        return deny(Reason.TASK_MISMATCH, "The grant does not authorize this task.")
    if scope is None:
        return deny(Reason.UNKNOWN_TASK, "No trusted task scope exists.")
    if grant.scope_version != scope.version:
        return deny(Reason.STALE_SCOPE, "The grant does not match the current scope version.")
    permission = Permission(request.operation, request.resource_id)
    if permission not in scope.permissions:
        return deny(Reason.OUTSIDE_SCOPE, "The operation/resource pair is outside the approved task scope.")
    if permission not in supported:
        return deny(Reason.UNSUPPORTED_ACTION, "No registered tool supports this operation/resource pair.")
    return Decision(Outcome.ALLOW, Reason.AUTHORIZED,
                    "Identity, grant, scope version and exact operation/resource pair match.",
                    principal_id, version)
