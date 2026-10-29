"""SQLite migrations and transactions for local effects and authority."""
from contextlib import closing, contextmanager
import os
from pathlib import Path
import sqlite3

from .contracts import GuardError

SCHEMA_VERSION = 2
SCHEMA = """
CREATE TABLE owner (singleton INTEGER PRIMARY KEY CHECK(singleton=1), uid INTEGER NOT NULL);
CREATE TABLE resources (resource_id TEXT NOT NULL, version INTEGER NOT NULL, content TEXT NOT NULL,
 digest TEXT NOT NULL, byte_count INTEGER NOT NULL CHECK(byte_count>=0), PRIMARY KEY(resource_id,version));
CREATE TABLE tasks (task_id TEXT PRIMARY KEY, current_version INTEGER NOT NULL,
 used_actions INTEGER NOT NULL DEFAULT 0 CHECK(used_actions>=0), used_bytes INTEGER NOT NULL DEFAULT 0 CHECK(used_bytes>=0));
CREATE TABLE scopes (task_id TEXT NOT NULL REFERENCES tasks(task_id), version INTEGER NOT NULL,
 body TEXT NOT NULL, approved_by INTEGER NOT NULL, reason TEXT NOT NULL, approved_at INTEGER NOT NULL,
 PRIMARY KEY(task_id,version));
CREATE TABLE grants (grant_id TEXT PRIMARY KEY, principal TEXT NOT NULL,
 task_id TEXT NOT NULL, scope_version INTEGER NOT NULL, expires_at INTEGER NOT NULL,
 revoked INTEGER NOT NULL DEFAULT 0 CHECK(revoked IN (0,1)),
 FOREIGN KEY(task_id,scope_version) REFERENCES scopes(task_id,version));
CREATE TABLE actions (request_id TEXT PRIMARY KEY, principal TEXT NOT NULL, fingerprint TEXT NOT NULL,
 body TEXT NOT NULL, scope_version INTEGER, status TEXT NOT NULL CHECK(status IN ('queued','completed','denied','cancelled')),
 reason TEXT NOT NULL, output TEXT, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);
CREATE TABLE notes (request_id TEXT PRIMARY KEY REFERENCES actions(request_id),
 resource_id TEXT NOT NULL, resource_version INTEGER NOT NULL, content TEXT NOT NULL,
 FOREIGN KEY(resource_id,resource_version) REFERENCES resources(resource_id,version));
CREATE TABLE receipts (request_id TEXT PRIMARY KEY REFERENCES actions(request_id),
 operation TEXT NOT NULL, resource_id TEXT NOT NULL, resource_version INTEGER NOT NULL,
 byte_count INTEGER NOT NULL, digest TEXT NOT NULL, completed_at INTEGER NOT NULL);
CREATE TABLE events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at INTEGER NOT NULL,
 kind TEXT NOT NULL, subject TEXT NOT NULL, details TEXT NOT NULL);
CREATE INDEX action_status ON actions(status);
CREATE TABLE labels (resource_id TEXT NOT NULL, version INTEGER NOT NULL, class TEXT NOT NULL,
 impact INTEGER NOT NULL CHECK(impact BETWEEN 1 AND 5), PRIMARY KEY(resource_id,version),
 FOREIGN KEY(resource_id,version) REFERENCES resources(resource_id,version));
CREATE TABLE traces (trace_id TEXT PRIMARY KEY, split TEXT NOT NULL, body TEXT NOT NULL, digest TEXT NOT NULL,
 reason TEXT NOT NULL, owner INTEGER NOT NULL);
CREATE TABLE profiles (task_id TEXT NOT NULL, version INTEGER NOT NULL, scope_version INTEGER NOT NULL,
 body TEXT NOT NULL, digest TEXT NOT NULL, PRIMARY KEY(task_id,version));
CREATE TABLE assessments (request_id TEXT PRIMARY KEY REFERENCES actions(request_id), body TEXT NOT NULL);
CREATE TABLE reviews (request_id TEXT PRIMARY KEY REFERENCES actions(request_id), profile_version INTEGER NOT NULL,
 scope_version INTEGER NOT NULL, reason TEXT NOT NULL);

"""


def owner_uid() -> int:
    if not hasattr(os, "getuid"):
        raise GuardError("unsupported_platform", "Phase two requires a POSIX OS (Linux/macOS, or Linux under WSL).")
    return os.getuid()


class Store:
    def __init__(self, path: Path):
        self.path = Path(path).absolute()
        self._check_file()

    def _check_file(self):
        if self.path.is_symlink() or not self.path.is_file():
            raise GuardError("store_unavailable", "Initialize a regular database file first; symlinks are not accepted.")
        stat = self.path.stat()
        if stat.st_uid != owner_uid() or stat.st_mode & 0o077:
            raise GuardError("owner_required", "Database must belong to the current OS user and have mode 0600.")

    @classmethod
    def initialize(cls, path: Path):
        path = Path(path).absolute()
        uid = owner_uid()
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as error:
            raise GuardError("already_initialized", "Database already exists; initialization never overwrites it.") from error
        os.close(fd)
        try:
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("BEGIN IMMEDIATE")
                for statement in SCHEMA.split(";"):
                    if statement.strip():
                        db.execute(statement)
                db.execute("INSERT INTO owner VALUES (1, ?)", (uid,))
                db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return cls(path)

    @contextmanager
    def transaction(self):
        self._check_file()
        db = None
        try:
            db = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=2)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            if db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
                raise GuardError("schema_mismatch", "Unsupported schema version; no automatic downgrade is permitted.")
            row = db.execute("SELECT uid FROM owner WHERE singleton=1").fetchone()
            if row is None or row[0] != owner_uid():
                raise GuardError("owner_required", "Administrative and runner access requires the recorded OS owner.")
            yield db
            db.commit()
        except sqlite3.Error as error:
            if db is not None:
                db.rollback()
            raise GuardError("store_unavailable", "Database operation failed; no success is asserted. Reconcile the request before retrying.") from error
        except BaseException:
            if db is not None:
                db.rollback()
            raise
        finally:
            if db is not None:
                db.close()
