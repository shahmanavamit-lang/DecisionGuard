"""Owner-only offline health, snapshot and fail-closed restore operations."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import time

from .storage import Store, SCHEMA_VERSION, owner_uid
from .contracts import GuardError


def validate(db):
    if db.execute('PRAGMA user_version').fetchone()[0] != SCHEMA_VERSION:
        raise GuardError('schema_mismatch', 'Only schema 4 is supported; no implicit migration.')
    if db.execute('SELECT uid FROM owner WHERE singleton=1').fetchone() != (owner_uid(),):
        raise GuardError('owner_required', 'Backup must belong to its recorded OS owner.')
    if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)] or db.execute('PRAGMA foreign_key_check').fetchone():
        raise GuardError('integrity_failure', 'Database integrity checks failed.')


def health(path):
    store = Store(path)
    with closing(sqlite3.connect(store.path.as_uri()+'?mode=ro', uri=True, timeout=2)) as db:
        db.execute('BEGIN')
        validate(db)
        running = db.execute("SELECT count(*) FROM worker_runs WHERE state='running'").fetchone()[0]
        queued = db.execute("SELECT count(*) FROM actions WHERE status='queued'").fetchone()[0]
        return {'integrity': 'ok', 'schema': SCHEMA_VERSION, 'running_records': running,
                'queued_actions': queued, 'recovery_review_required': bool(running),
                'bytes': store.path.stat().st_size}


def snapshot(source, destination, *, restore=False):
    """SQLite backup API includes committed WAL pages; never overwrite a destination."""
    store = Store(source)
    destination = Path(destination).absolute()
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        with closing(sqlite3.connect(store.path.as_uri()+'?mode=ro', uri=True, timeout=2)) as src, closing(sqlite3.connect(destination)) as dst:
            deadline = time.monotonic()+10
            def progress(status, remaining, total):
                if time.monotonic()>deadline:
                    raise TimeoutError('Backup exceeded ten seconds; retry after stopping writers.')
            src.backup(dst, pages=256, progress=progress, sleep=0.05)
            validate(dst)
            if restore:
                with dst:
                    dst.execute('UPDATE grants SET revoked=1')
                    dst.execute('UPDATE contexts SET quarantined=1')
                    dst.execute('UPDATE nodes SET quarantined=1')
                    dst.execute("UPDATE actions SET status='cancelled',reason='restore_requires_review',updated_at=? WHERE status='queued'", (int(time.time()),))
                    dst.execute("UPDATE worker_runs SET state='stopped' WHERE state='running'")
                    dst.execute('INSERT INTO events(occurred_at,kind,subject,details) VALUES(?,?,?,?)',
                                (int(time.time()), 'restore_locked', 'store', json.dumps({'authority_disabled': True, 'later_receipts_may_be_missing': True})))
            validate(dst)
        return {'operation': 'restore' if restore else 'backup', 'schema': SCHEMA_VERSION,
                'authority_disabled': restore, 'destination': str(destination)}
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
