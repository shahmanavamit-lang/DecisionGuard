"""Immutable contracts. Proposed actions never carry authoritative permissions."""
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
import re


class ValidationError(ValueError):
    """A request or trusted configuration violates the contract."""


def identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,79}", value):
        raise ValidationError(f"{field} must be a 1–80 character identifier")
    return value


@dataclass(frozen=True)
class Permission:
    operation: str
    resource_id: str

    def __post_init__(self) -> None:
        identifier(self.operation, "operation")
        identifier(self.resource_id, "resource_id")


@dataclass(frozen=True)
class TaskScope:
    task_id: str
    version: int
    description: str
    permissions: frozenset[Permission]

    def __post_init__(self) -> None:
        identifier(self.task_id, "task_id")
        if type(self.version) is not int or self.version < 1:
            raise ValidationError("scope version must be a positive integer")
        if not isinstance(self.description, str) or not 1 <= len(self.description) <= 500:
            raise ValidationError("description must contain 1–500 characters")
        if not isinstance(self.permissions, frozenset) or not all(isinstance(p, Permission) for p in self.permissions):
            raise ValidationError("permissions must be a frozenset of Permission")


@dataclass(frozen=True)
class Grant:
    grant_id: str
    principal_id: str
    task_id: str
    scope_version: int

    def __post_init__(self) -> None:
        for field in ("grant_id", "principal_id", "task_id"):
            identifier(getattr(self, field), field)
        if type(self.scope_version) is not int or self.scope_version < 1:
            raise ValidationError("scope_version must be a positive integer")


@dataclass(frozen=True)
class ActionRequest:
    request_id: str
    task_id: str
    grant_id: str
    operation: str
    resource_id: str

    def __post_init__(self) -> None:
        for field in self.__dataclass_fields__:
            identifier(getattr(self, field), field)

    @classmethod
    def from_dict(cls, data: Any) -> "ActionRequest":
        if not isinstance(data, dict):
            raise ValidationError("action must be a JSON object")
        expected = set(cls.__dataclass_fields__)
        if set(data) != expected:
            raise ValidationError("action must contain exactly: " + ", ".join(sorted(expected)))
        return cls(**data)


class Outcome(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class Reason(StrEnum):
    AUTHENTICATION_REQUIRED = "authentication_required"
    UNKNOWN_GRANT = "unknown_grant"
    PRINCIPAL_MISMATCH = "principal_mismatch"
    TASK_MISMATCH = "task_mismatch"
    UNKNOWN_TASK = "unknown_task"
    STALE_SCOPE = "stale_scope"
    OUTSIDE_SCOPE = "outside_scope"
    UNSUPPORTED_ACTION = "unsupported_action"
    AUTHORIZED = "authorized"


@dataclass(frozen=True)
class Decision:
    outcome: Outcome
    reason: Reason
    explanation: str
    principal_id: str | None
    scope_version: int | None


@dataclass(frozen=True)
class Receipt:
    receipt_id: str
    request_id: str
    operation: str
    resource_id: str
    completed_at: str


@dataclass(frozen=True)
class Event:
    event_id: str
    occurred_at: str
    request: ActionRequest
    decision: Decision
    execution_status: str
    receipt_id: str | None


@dataclass(frozen=True)
class ExecutionResult:
    decision: Decision
    event: Event
    receipt: Receipt | None
    output: dict[str, object] | None
