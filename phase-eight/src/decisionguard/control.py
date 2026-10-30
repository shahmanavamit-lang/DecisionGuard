"""Owner read models and narrow, audited controls shared by CLI and optional console."""
import json
from uuid import uuid4

from .broker import run_worker, stop_worker, validate_plan
from .contracts import Scope, canonical, exact, identifier, integer, require
from .storage import owner_uid

LIMIT = 200


def snapshot(engine):
    """One consistent, bounded view. Counts describe the full store, not the page."""
    with engine.store.transaction() as db:
        clipped = []
        def rows(name, sql):
            result = [dict(r) for r in db.execute(sql, (LIMIT + 1,))]
            if len(result) > LIMIT:
                clipped.append(name)
            return result[:LIMIT]
        tasks = rows('tasks', 'SELECT t.*,s.body,s.reason,s.approved_at, EXISTS(SELECT 1 FROM managed_tasks m WHERE m.task_id=t.task_id) AS managed FROM tasks t JOIN scopes s ON s.task_id=t.task_id AND s.version=t.current_version ORDER BY t.task_id LIMIT ?')
        for task in tasks:
            task['scope'] = json.loads(task.pop('body'))
        actions = rows('actions', 'SELECT request_id,principal,body,scope_version,status,reason,created_at,updated_at FROM actions ORDER BY created_at DESC,request_id DESC LIMIT ?')
        for action in actions:
            body = json.loads(action.pop('body'))
            body.pop('content', None)
            action.update(body)
            if action['status'] == 'queued' and action['reason'] == 'behavior_review':
                action['status'] = 'held'
            evidence = db.execute('SELECT body FROM assessments WHERE request_id=?', (action['request_id'],)).fetchone()
            action['behavior'] = json.loads(evidence[0]) if evidence else None
            receipt = db.execute('SELECT * FROM receipts WHERE request_id=?', (action['request_id'],)).fetchone()
            action['receipt'] = dict(receipt) if receipt else None
        runs = rows('runs', 'SELECT w.*,g.task_id FROM worker_runs w JOIN contexts c ON c.context_id=w.context_id JOIN grants g ON g.grant_id=c.grant_id ORDER BY w.rowid DESC LIMIT ?')
        for run in runs:
            run['report'] = json.loads(run.pop('body'))
        counts = {table: db.execute('SELECT count(*) FROM '+table).fetchone()[0]
                  for table in ('tasks', 'actions', 'receipts', 'worker_runs')}
        counts['held'] = db.execute("SELECT count(*) FROM actions WHERE status='queued' AND reason='behavior_review'").fetchone()[0]
        counts['denied'] = db.execute("SELECT count(*) FROM actions WHERE status='denied'").fetchone()[0]
        counts['quarantined'] = db.execute('SELECT count(*) FROM contexts WHERE quarantined=1').fetchone()[0]
        return {'counts': counts, 'tasks': tasks, 'actions': actions, 'runs': runs,
                'grants': rows('grants', 'SELECT * FROM grants ORDER BY rowid DESC LIMIT ?'),
                'contexts': rows('contexts', 'SELECT c.*,g.task_id FROM contexts c JOIN grants g ON g.grant_id=c.grant_id ORDER BY c.rowid DESC LIMIT ?'),
                'resources': rows('resources', 'SELECT r.resource_id,r.version,r.digest,r.byte_count,l.class,l.impact FROM resources r LEFT JOIN labels l ON r.resource_id=l.resource_id AND r.version=l.version ORDER BY r.rowid DESC LIMIT ?'),
                'truncated': clipped, 'limit': LIMIT, 'observed_at': engine.clock(),
                'latest_sequence': db.execute('SELECT coalesce(max(sequence),0) FROM events').fetchone()[0]}


def timeline(engine, before=0):
    integer(before, 0)
    with engine.store.transaction() as db:
        events = [dict(r) for r in db.execute('SELECT * FROM events WHERE (?=0 OR sequence<?) ORDER BY sequence DESC LIMIT ?', (before, before, LIMIT+1))]
        more = len(events) > LIMIT
        events = events[:LIMIT]
        for event in events:
            event['details'] = json.loads(event['details'])
        return {'events': events, 'next_before': events[-1]['sequence'] if more else None}


def graph(engine, task_id):
    identifier(task_id)
    with engine.store.transaction() as db:
        # Include all ancestors of task contexts, including dependencies from other tasks.
        nodes = [dict(r) for r in db.execute('''WITH RECURSIVE related(id) AS (
            SELECT n.node_id FROM nodes n JOIN contexts c ON c.context_id=n.context_id
                JOIN grants g ON g.grant_id=c.grant_id WHERE g.task_id=?
            UNION SELECT e.source FROM edges e JOIN related r ON e.target=r.id)
            SELECT n.* FROM nodes n JOIN related r ON r.id=n.node_id ORDER BY n.node_id LIMIT ?''', (task_id, LIMIT+1))]
        partial = len(nodes) > LIMIT
        nodes = nodes[:LIMIT]
        ids = [n['node_id'] for n in nodes]
        edges = []
        if ids:
            marks = ','.join('?' for _ in ids)
            edges = [dict(r) for r in db.execute(f'SELECT * FROM edges WHERE source IN ({marks}) AND target IN ({marks}) ORDER BY source,target LIMIT ?', (*ids, *ids, LIMIT*4+1))]
        partial = partial or len(edges) > LIMIT*4
        return {'nodes': nodes, 'edges': edges[:LIMIT*4], 'partial': partial,
                'meaning': 'Recorded dependencies only. Clean-looking nodes are not a reusable permission to continue.'}


def action_detail(engine, request_id):
    identifier(request_id)
    with engine.store.transaction() as db:
        row = db.execute('SELECT * FROM actions WHERE request_id=?', (request_id,)).fetchone()
        require(row is not None, 'Unknown action.')
        result = engine._result(db, request_id)
        result['proposal'] = json.loads(row['body'])
        result['review'] = None
        review = db.execute('SELECT * FROM reviews WHERE request_id=?', (request_id,)).fetchone()
        if review:
            result['review'] = dict(review)
        context = engine._context(db, result['proposal']['grant_id'])
        result['context'] = dict(context) if context else None
        return result


def _reason(data):
    reason = data.get('reason')
    require(isinstance(reason, str) and 0 < len(reason.strip()) <= 500, 'Supply a 1–500 character owner reason.')
    return reason


def prepare_fresh_context(engine, data):
    """Explicit owner-authorized clean start; never copy contaminated memory/grants."""
    exact(data, {'task_id', 'expected_version', 'run_id', 'plan', 'reason'})
    for name in ('task_id', 'run_id'):
        identifier(data[name])
    require(len(data['run_id']) <= 70, 'Run ID is too long.')
    integer(data['expected_version']); _reason(data); validate_plan(data['plan'])
    suffix = uuid4().hex
    grant_id, context_id, memory_id = 'ui-g-'+suffix, 'ui-c-'+suffix, 'ui-m-'+suffix
    with engine.store.transaction() as db:
        task = db.execute('SELECT current_version FROM tasks WHERE task_id=?', (data['task_id'],)).fetchone()
        require(task is not None and task[0] == data['expected_version'], 'Task scope changed. Refresh and review it first.')
        require(db.execute('SELECT 1 FROM managed_tasks WHERE task_id=?', (data['task_id'],)).fetchone(), 'Enroll this task with the manage CLI command first.')
        require(not db.execute('SELECT 1 FROM worker_runs WHERE run_id=?', (data['run_id'],)).fetchone(), 'Run ID already used. Inspect its receipts; do not replay it.')
        for index in range(len(data['plan']['steps'])):
            require(not db.execute('SELECT 1 FROM actions WHERE request_id=?', (f"{data['run_id']}.{index}",)).fetchone(), 'A step ID already exists. Inspect it before choosing a new run ID.')
        db.execute('INSERT INTO grants(grant_id,principal,task_id,scope_version,expires_at) VALUES(?,?,?,?,?)', (grant_id, 'local-worker', data['task_id'], task[0], engine.clock()+600))
        db.execute('INSERT INTO contexts VALUES(?,?,?,0,0)', (context_id, grant_id, memory_id))
        db.execute('INSERT INTO nodes VALUES(?,?,0)', ('c:'+context_id+':0', context_id))
        engine._event(db, 'console_fresh_context', context_id, {'grant_id':grant_id, 'memory_id':memory_id, 'task_id':data['task_id'], 'scope_version':task[0], 'run_id':data['run_id'], 'reason':data['reason'], 'approved_by_uid':owner_uid()})
    return context_id


def mutate(engine, operation, data):
    require(isinstance(data, dict), 'Expected a JSON object.')
    reason = _reason(data)
    if operation == 'approve':
        exact(data, {'scope', 'expected_version', 'reason'})
        integer(data['expected_version'], 0)
        return engine.approve(Scope.from_dict(data['scope']), reason=reason, expected_version=data['expected_version'])
    if operation == 'start':
        context = prepare_fresh_context(engine, data)
        # A failure here may leave an unused context. Events identify it for reconciliation.
        return run_worker(engine, context, data['run_id'], data['plan'])
    if operation == 'contain':
        exact(data, {'context_id', 'reason', 'unknown_lineage'})
        require(type(data['unknown_lineage']) is bool, 'unknown_lineage must be boolean.')
        return engine.contain(data['context_id'], reason, data['unknown_lineage'])
    if operation == 'stop':
        exact(data, {'run_id', 'reason'})
        return stop_worker(engine, data['run_id'], reason)
    require(operation in ('review', 'dispatch', 'continuation'), 'Unknown console operation.')
    exact(data, {'request_id', 'reason'})
    identifier(data['request_id'])
    if operation == 'review':
        return engine.review(data['request_id'], reason)
    if operation == 'continuation':
        return engine.continuation(data['request_id'])
    with engine.store.transaction() as db:
        row = db.execute('SELECT principal FROM actions WHERE request_id=?', (data['request_id'],)).fetchone()
        require(row is not None, 'Unknown action.')
        engine._event(db, 'console_dispatch_requested', data['request_id'], {'reason':reason, 'approved_by_uid':owner_uid()})
        principal = row[0]
    return engine.dispatch(data['request_id'], principal=principal)
