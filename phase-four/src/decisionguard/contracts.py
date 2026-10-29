"""Strict data contracts; authority cannot be supplied in an action."""
from dataclasses import asdict, dataclass
import json
import re
from pathlib import Path

MAX_FILE_BYTES = 1_048_576


class GuardError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GuardError("invalid_input", message)


def identifier(value: object) -> str:
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}", value) is not None,
            "Identifiers must contain 1–80 letters, digits, underscores, dots, colons or hyphens.")
    return value


def integer(value: object, minimum: int = 1) -> int:
    require(type(value) is int and minimum <= value <= 2**53 - 1, "Expected a bounded integer.")
    return value


def exact(data: object, fields: set[str]) -> None:
    require(isinstance(data, dict) and set(data) == fields, "Expected exactly these fields: " + ", ".join(sorted(fields)))


def canonical(data: object) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def read_json(path: Path) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate JSON keys are not allowed.")
            result[key] = value
        return result
    with path.open("rb") as stream:
        raw = stream.read(MAX_FILE_BYTES + 1)
    require(len(raw) <= MAX_FILE_BYTES, "JSON input exceeds 1 MiB.")
    try:
        return json.loads(raw, object_pairs_hook=unique)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise GuardError("invalid_input", "Input must be valid UTF-8 JSON.") from error


@dataclass(frozen=True)
class Permission:
    operation: str
    resource_id: str
    resource_version: int

    def __post_init__(self):
        require(self.operation in ("read_file", "write_note"), "Unsupported operation.")
        identifier(self.resource_id)
        integer(self.resource_version)


@dataclass(frozen=True)
class Scope:
    task_id: str
    description: str
    permissions: tuple[Permission, ...]
    max_actions: int
    max_bytes: int

    def __post_init__(self):
        identifier(self.task_id)
        require(isinstance(self.description, str) and 0 < len(self.description) <= 500, "Description must contain 1–500 characters.")
        require(isinstance(self.permissions, tuple) and 0 < len(self.permissions) <= 100 and
                all(isinstance(p, Permission) for p in self.permissions), "Supply 1–100 permissions.")
        require(len(set(self.permissions)) == len(self.permissions), "Duplicate permissions are not allowed.")
        integer(self.max_actions)
        integer(self.max_bytes, 0)

    @classmethod
    def from_dict(cls, data):
        exact(data, {"task_id", "description", "permissions", "max_actions", "max_bytes"})
        require(isinstance(data["permissions"], list), "permissions must be an array.")
        permissions = []
        for p in data["permissions"]:
            exact(p, {"operation", "resource_id", "resource_version"})
            permissions.append(Permission(**p))
        return cls(**{**data, "permissions": tuple(permissions)})


@dataclass(frozen=True)
class Action:
    request_id: str
    task_id: str
    grant_id: str
    operation: str
    resource_id: str
    resource_version: int
    content: str = ""

    def __post_init__(self):
        for value in (self.request_id, self.task_id, self.grant_id, self.resource_id):
            identifier(value)
        Permission(self.operation, self.resource_id, self.resource_version)
        require(isinstance(self.content, str), "content must be text.")
        try:
            size = len(self.content.encode("utf-8"))
        except UnicodeError as error:
            raise GuardError("invalid_input", "content must be valid UTF-8 text.") from error
        require(size <= MAX_FILE_BYTES, "content exceeds 1 MiB.")
        require(self.operation != "read_file" or not self.content, "read_file cannot carry content.")
        require(self.operation != "write_note" or bool(self.content), "write_note requires nonempty content.")

    @classmethod
    def from_dict(cls, data):
        require(isinstance(data, dict), "Action must be an object.")
        exact(data, {"request_id", "task_id", "grant_id", "operation", "resource_id", "resource_version"} |
              ({"content"} if "content" in data else set()))
        return cls(**data)

    def to_dict(self):
        return asdict(self)
