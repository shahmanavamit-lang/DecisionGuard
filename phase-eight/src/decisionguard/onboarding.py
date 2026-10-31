"""Presentation adapter: explicit owner approval using existing engine operations."""
from pathlib import Path
import tempfile
from .contracts import Scope, Permission, MAX_FILE_BYTES, exact, identifier, require


def prepare(engine, data):
    exact(data, {'task_id', 'description', 'content', 'reason', 'confirmed'})
    identifier(data['task_id'])
    require(data['confirmed'] is True, 'Review and approve the displayed permissions first.')
    require(isinstance(data['content'], str), 'Choose a UTF-8 text file.')
    raw = data['content'].encode('utf-8')
    # JSON escaping may expand the HTTP body; keep the guided upload comfortably bounded.
    require(0 < len(raw) <= min(MAX_FILE_BYTES, 200_000), 'Choose a non-empty UTF-8 text file up to 200 KB.')
    require(isinstance(data['reason'], str) and 0 < len(data['reason'].strip()) <= 500, 'Supply an approval reason.')
    resource = data['task_id']
    scope = Scope(data['task_id'], data['description'],
                  (Permission('read_file', resource, 1), Permission('write_note', resource, 1)),
                  2, len(raw)+4096)
    # Reject reused IDs before importing. A duplicate/retry must not rerun work.
    # Each operation retains its own transaction and audit evidence. A partial setup
    # grants no worker authority; inspect the record before explicitly starting anew.
    with engine.store.transaction() as db:
        require(not db.execute('SELECT 1 FROM tasks WHERE task_id=?', (data['task_id'],)).fetchone(),
                'This task already exists. Inspect its recorded results before starting again.')
        require(not db.execute('SELECT 1 FROM resources WHERE resource_id=?', (resource,)).fetchone(),
                'This setup ID already exists. Inspect its recorded results before starting again.')
    with tempfile.TemporaryDirectory(prefix='decisionguard-upload-') as folder:
        path = Path(folder)/'input.txt'
        path.write_bytes(raw)
        imported = engine.import_file(resource, path)
    require(imported['resource_version'] == 1, 'File version changed during setup. Inspect Permissions before continuing.')
    engine.label(resource, 1, 'document', 2)
    engine.approve(scope, reason=data['reason'], expected_version=0)
    engine.manage(data['task_id'])
    return {'task_id':data['task_id'], 'scope_version':1, 'resource_id':resource,
            'resource_version':1, 'bytes':len(raw), 'max_actions':2, 'max_bytes':len(raw)+4096,
            'state':'ready', 'message':'File imported and permissions approved. No worker has run yet.'}
