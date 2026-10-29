"""Local owner administration and atomic, task-scoped execution."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

from .contracts import Action, GuardError, MAX_FILE_BYTES, Permission, Scope, canonical, identifier, integer, require
from .storage import Store, owner_uid


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


from .learning import Learning


class Engine(Learning):
    def __init__(self, path: Path, *, clock=None):
        self.store = Store(path)
        self.clock = clock if clock is not None else lambda: int(time.time())

    def _event(self, db, kind, subject, details):
        db.execute("INSERT INTO events(occurred_at,kind,subject,details) VALUES(?,?,?,?)",
                   (self.clock(), kind, subject, canonical(details)))

    def import_file(self, resource_id: str, path: Path):
        identifier(resource_id)
        with Path(path).open("rb") as stream:
            raw = stream.read(MAX_FILE_BYTES + 1)
        require(len(raw) <= MAX_FILE_BYTES, "Resource exceeds 1 MiB.")
        try:
            content = raw.decode("utf-8")
        except UnicodeError as error:
            raise GuardError("invalid_input", "Resource must be a UTF-8 text file.") from error
        with self.store.transaction() as db:
            version = db.execute("SELECT coalesce(max(version),0)+1 FROM resources WHERE resource_id=?", (resource_id,)).fetchone()[0]
            db.execute("INSERT INTO resources VALUES(?,?,?,?,?)", (resource_id, version, content, digest(content), len(raw)))
            self._event(db, "resource_imported", resource_id, {"version": version, "digest": digest(content), "bytes": len(raw)})
            return {"resource_id": resource_id, "resource_version": version, "sha256": digest(content), "bytes": len(raw)}

    def approve(self, scope: Scope, *, reason: str):
        require(isinstance(scope, Scope), "Expected a validated Scope.")
        require(isinstance(reason, str) and 0 < len(reason) <= 500, "Approval requires a 1–500 character reason.")
        with self.store.transaction() as db:
            for p in scope.permissions:
                require(db.execute("SELECT 1 FROM resources WHERE resource_id=? AND version=?", (p.resource_id, p.resource_version)).fetchone() is not None,
                        "Every permission must name an imported resource version.")
            row = db.execute("SELECT current_version FROM tasks WHERE task_id=?", (scope.task_id,)).fetchone()
            version = row[0] + 1 if row else 1
            if row:
                db.execute("UPDATE tasks SET current_version=? WHERE task_id=?", (version, scope.task_id))
            else:
                db.execute("INSERT INTO tasks(task_id,current_version) VALUES(?,?)", (scope.task_id, version))
            db.execute("INSERT INTO scopes VALUES(?,?,?,?,?,?)", (scope.task_id, version, canonical(asdict(scope)), owner_uid(), reason, self.clock()))
            self._event(db, "scope_approved", scope.task_id, {"scope_version": version, "approved_by_uid": owner_uid(), "reason": reason})
            return {"task_id": scope.task_id, "scope_version": version}

    def grant(self, grant_id: str, principal: str, task_id: str, *, ttl: int):
        for value in (grant_id, principal, task_id):
            identifier(value)
        integer(ttl)
        require(ttl <= 31_536_000, "Grant duration must not exceed one year.")
        with self.store.transaction() as db:
            row = db.execute("SELECT current_version FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            require(row is not None, "Approve the task scope first.")
            require(db.execute("SELECT 1 FROM grants WHERE grant_id=?", (grant_id,)).fetchone() is None, "Grant ID already exists; choose a new ID.")
            expires_at = self.clock() + ttl
            db.execute("INSERT INTO grants(grant_id,principal,task_id,scope_version,expires_at) VALUES(?,?,?,?,?)",
                       (grant_id, principal, task_id, row[0], expires_at))
            self._event(db, "grant_issued", grant_id, {"principal": principal, "task_id": task_id, "scope_version": row[0], "expires_at": expires_at})
            return {"grant_id": grant_id, "scope_version": row[0], "expires_at": expires_at}

    def revoke(self, grant_id: str):
        identifier(grant_id)
        with self.store.transaction() as db:
            require(db.execute("SELECT 1 FROM grants WHERE grant_id=?", (grant_id,)).fetchone() is not None, "Unknown grant.")
            db.execute("UPDATE grants SET revoked=1 WHERE grant_id=?", (grant_id,))
            cancelled = 0
            for row in db.execute("SELECT request_id,body FROM actions WHERE status='queued'").fetchall():
                if json.loads(row['body'])['grant_id'] == grant_id:
                    db.execute("UPDATE actions SET status='cancelled',reason='grant_revoked',updated_at=? WHERE request_id=?", (self.clock(), row['request_id']))
                    self._event(db, "action_cancelled", row['request_id'], {"reason": "grant_revoked"})
                    cancelled += 1
            self._event(db, "grant_revoked", grant_id, {"cancelled": cancelled})
            return {"grant_id": grant_id, "revoked": True, "cancelled": cancelled}

    def _assess(self, db, action: Action, principal: str):
        grant = db.execute("SELECT * FROM grants WHERE grant_id=?", (action.grant_id,)).fetchone()
        if grant is None:
            return "unknown_grant", None, 0
        version = grant['scope_version']
        for invalid, reason in ((grant['principal'] != principal, "principal_mismatch"),
                                (grant['task_id'] != action.task_id, "task_mismatch"),
                                (bool(grant['revoked']), "grant_revoked"),
                                (grant['expires_at'] <= self.clock(), "grant_expired")):
            if invalid:
                return reason, version, 0
        task = db.execute("SELECT * FROM tasks WHERE task_id=?", (action.task_id,)).fetchone()
        if task is None or task['current_version'] != version:
            return "stale_scope", version, 0
        scope = Scope.from_dict(json.loads(db.execute("SELECT body FROM scopes WHERE task_id=? AND version=?", (action.task_id, version)).fetchone()[0]))
        if Permission(action.operation, action.resource_id, action.resource_version) not in scope.permissions:
            return "outside_scope", version, 0
        resource = db.execute("SELECT * FROM resources WHERE resource_id=? AND version=?", (action.resource_id, action.resource_version)).fetchone()
        if resource is None:
            return "missing_resource", version, 0
        if digest(resource['content']) != resource['digest'] or len(resource['content'].encode('utf-8')) != resource['byte_count']:
            return "resource_integrity", version, 0
        cost = resource['byte_count'] if action.operation == 'read_file' else len(action.content.encode('utf-8'))
        if task['used_actions'] + 1 > scope.max_actions or task['used_bytes'] + cost > scope.max_bytes:
            return "budget_exceeded", version, cost
        return "authorized", version, cost

    def submit(self, action: Action, *, principal: str):
        require(isinstance(action, Action), "Expected a validated Action.")
        identifier(principal)
        fingerprint = digest(canonical({"principal": principal, "action": action.to_dict()}))
        with self.store.transaction() as db:
            existing = db.execute("SELECT * FROM actions WHERE request_id=?", (action.request_id,)).fetchone()
            if existing:
                if existing['fingerprint'] != fingerprint:
                    raise GuardError("idempotency_conflict", "Request ID already belongs to different content or a different principal.")
                return self._result(db, action.request_id)
            reason, version, cost = self._assess(db, action, principal)
            state = 'queued' if reason == 'authorized' else 'denied'
            now = self.clock()
            db.execute("INSERT INTO actions VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (action.request_id, principal, fingerprint, canonical(action.to_dict()), version, state, reason, None, now, now))
            evidence = self._behavior(db, action, reason, version, cost)
            db.execute('INSERT INTO assessments VALUES(?,?)',(action.request_id,canonical(evidence)))
            self._event(db, "action_submitted", action.request_id, {"principal": principal, "status": state, "reason": reason, "scope_version": version})
            return self._result(db, action.request_id)

    def dispatch(self, request_id: str, *, principal: str):
        identifier(request_id)
        identifier(principal)
        with self.store.transaction() as db:
            row = db.execute("SELECT * FROM actions WHERE request_id=?", (request_id,)).fetchone()
            if row is None:
                raise GuardError("not_found", "Unknown request.")
            if row['principal'] != principal:
                raise GuardError("principal_mismatch", "This request belongs to another runner identity.")
            if row['status'] != 'queued':
                return self._result(db, request_id)
            action = Action.from_dict(json.loads(row['body']))
            reason, version, cost = self._assess(db, action, principal)
            evidence = self._behavior(db, action, reason, version, cost)
            db.execute('INSERT OR REPLACE INTO assessments VALUES(?,?)',(request_id,canonical(evidence)))
            if reason != 'authorized':
                db.execute("UPDATE actions SET status='denied',reason=?,updated_at=? WHERE request_id=?", (reason, self.clock(), request_id))
                self._event(db, 'dispatch_denied', request_id, {"reason": reason, "scope_version": version})
                return self._result(db, request_id)
            review = db.execute('SELECT * FROM reviews WHERE request_id=?',(request_id,)).fetchone()
            released = review and review['profile_version']==evidence['profile_version'] and review['scope_version']==version
            if evidence['hold_required'] and not released:
                db.execute("UPDATE actions SET reason='behavior_review',updated_at=? WHERE request_id=?",(self.clock(),request_id))
                self._event(db,'behavior_held',request_id,evidence)
                return self._result(db,request_id)
            if action.operation == 'read_file':
                content = db.execute("SELECT content FROM resources WHERE resource_id=? AND version=?", (action.resource_id, action.resource_version)).fetchone()[0]
                output = {"content": content, "resource_version": action.resource_version}
            else:
                content = action.content
                db.execute("INSERT INTO notes VALUES(?,?,?,?)", (request_id, action.resource_id, action.resource_version, content))
                output = {"note_id": request_id, "sha256": digest(content)}
            self._after_effect(db)  # Private test seam for crash/rollback verification.
            now = self.clock()
            db.execute("INSERT INTO receipts VALUES(?,?,?,?,?,?,?)", (request_id, action.operation, action.resource_id, action.resource_version, cost, digest(content), now))
            db.execute("UPDATE tasks SET used_actions=used_actions+1,used_bytes=used_bytes+? WHERE task_id=?", (cost, action.task_id))
            db.execute("UPDATE actions SET status='completed',reason='authorized',output=?,updated_at=? WHERE request_id=?", (canonical(output), now, request_id))
            self._event(db, 'action_completed', request_id, {"scope_version": version, "bytes": cost, "receipt_id": request_id})
            return self._result(db, request_id)

    def _after_effect(self, db):
        pass

    def _result(self, db, request_id):
        row = db.execute("SELECT * FROM actions WHERE request_id=?", (request_id,)).fetchone()
        receipt = db.execute("SELECT * FROM receipts WHERE request_id=?", (request_id,)).fetchone()
        evidence = db.execute('SELECT body FROM assessments WHERE request_id=?',(request_id,)).fetchone()
        return {"behavior": json.loads(evidence[0]) if evidence else None,
                "request_id": request_id, "principal": row['principal'], "status": 'held' if row['status']=='queued' and row['reason']=='behavior_review' else row['status'],
                "reason": row['reason'], "scope_version": row['scope_version'],
                "output": json.loads(row['output']) if row['output'] else None,
                "receipt": dict(receipt) if receipt else None}

    def reconcile(self, request_id: str):
        identifier(request_id)
        with self.store.transaction() as db:
            if db.execute("SELECT 1 FROM actions WHERE request_id=?", (request_id,)).fetchone() is None:
                return {"request_id": request_id, "status": "not_found", "receipt": None}
            return self._result(db, request_id)

    def inspect(self):
        with self.store.transaction() as db:
            return {"tasks": [dict(r) for r in db.execute('SELECT * FROM tasks ORDER BY task_id')],
                    "resources": [dict(r) for r in db.execute('SELECT resource_id,version,digest,byte_count FROM resources ORDER BY resource_id,version')],
                    "grants": [dict(r) for r in db.execute('SELECT * FROM grants ORDER BY grant_id')],
                    "actions": [self._result(db, r[0]) for r in db.execute('SELECT request_id FROM actions ORDER BY created_at,request_id').fetchall()],
                    "note_count": db.execute('SELECT count(*) FROM notes').fetchone()[0],
                    "receipt_count": db.execute('SELECT count(*) FROM receipts').fetchone()[0]}

    def events(self):
        with self.store.transaction() as db:
            return [{**dict(r), "details": json.loads(r['details'])} for r in db.execute('SELECT * FROM events ORDER BY sequence')]
