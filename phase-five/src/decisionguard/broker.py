"""Owner-side broker: narrow protocol, bounded subprocess and current authority."""
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import time

from .behavior import sha
from .contracts import Action, GuardError, canonical, exact, identifier, integer, require
from .engine import Engine

MAX_FRAME = 8 * 1024 * 1024


def validate_plan(plan):
    exact(plan, {'steps'})
    require(isinstance(plan['steps'], list) and 1 <= len(plan['steps']) <= 100, 'Plan must contain 1–100 steps.')
    sources = set()
    for index, step in enumerate(plan['steps']):
        require(isinstance(step, dict), 'Step must be an object.')
        kind = step.get('kind')
        if kind == 'receive':
            exact(step, {'kind', 'output_id'}); identifier(step['output_id']); sources.add(index)
        else:
            require(kind in ('read', 'summarize'), 'Only read, summarize and receive steps are supported.')
            fields = {'kind', 'resource_id', 'resource_version'} | ({'source'} if kind == 'summarize' else set())
            exact(step, fields); identifier(step['resource_id']); integer(step['resource_version'])
            if kind == 'summarize':
                integer(step['source'], 0)
                require(step['source'] in sources, 'Summary source must refer to an earlier read or receive step.')
            else:
                sources.add(index)
    return plan


class Channel:
    def __init__(self, process, deadline):
        self.process = process
        self.deadline = deadline
        self.pending = bytearray()
        os.set_blocking(process.stdout.fileno(), False)
        os.set_blocking(process.stdin.fileno(), False)

    def _wait(self, stream, event):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise GuardError('worker_timeout', 'Worker deadline exceeded.')
        with selectors.DefaultSelector() as selector:
            selector.register(stream, event)
            if not selector.select(remaining):
                raise GuardError('worker_timeout', 'Worker deadline exceeded.')

    def write(self, data):
        payload = canonical(data).encode() + b'\n'
        require(len(payload) <= MAX_FRAME, 'Broker response exceeds frame limit.')
        while payload:
            self._wait(self.process.stdin, selectors.EVENT_WRITE)
            try:
                count = os.write(self.process.stdin.fileno(), payload)
            except BlockingIOError:
                continue
            payload = payload[count:]

    def read(self):
        while b'\n' not in self.pending:
            self._wait(self.process.stdout, selectors.EVENT_READ)
            try:
                chunk = os.read(self.process.stdout.fileno(), 65536)
            except BlockingIOError:
                continue
            if not chunk:
                raise GuardError('worker_exited', 'Worker exited before completing the protocol.')
            self.pending.extend(chunk)
            require(len(self.pending) <= MAX_FRAME, 'Worker response exceeds frame limit.')
        line, _, rest = self.pending.partition(b'\n')
        self.pending = bytearray(rest)
        def unique(pairs):
            result = {}
            for key, value in pairs:
                require(key not in result, 'Duplicate protocol field.')
                result[key] = value
            return result
        try:
            return json.loads(line, object_pairs_hook=unique)
        except (ValueError, UnicodeError, RecursionError) as error:
            raise GuardError('worker_protocol', 'Worker sent invalid JSON.') from error


def proposal_action(message, step, index, run_id, task_id, grant_id):
    exact(message, {'kind', 'index', 'operation', 'resource_id', 'resource_version', 'content'})
    require(message['kind'] == 'action' and type(message['index']) is int and message['index'] == index, 'Unexpected proposal order.')
    require(message['resource_id'] == step['resource_id'] and message['resource_version'] == step['resource_version'], 'Worker changed the configured resource.')
    require(message['operation'] == ('read_file' if step['kind'] == 'read' else 'write_note'), 'Worker changed operation.')
    # Task, grant, principal and request IDs are bound by the broker, never the worker.
    return Action(f'{run_id}.{index}', task_id, grant_id, message['operation'],
                  message['resource_id'], message['resource_version'], message['content'])


def run_worker(engine, context_id, run_id, plan, *, timeout=10):
    validate_plan(plan); identifier(context_id); identifier(run_id)
    require(len(run_id) <= 70, 'Run ID must leave room for step identifiers.')
    require(type(timeout) in (int, float) and 0 < timeout <= 60, 'Timeout must be 0–60 seconds.')
    with engine.store.transaction() as db:
        context = db.execute('SELECT * FROM contexts WHERE context_id=?', (context_id,)).fetchone()
        require(context is not None and not context['quarantined'], 'A clean managed context is required.')
        grant = db.execute('SELECT * FROM grants WHERE grant_id=?', (context['grant_id'],)).fetchone()
        require(grant is not None and not grant['revoked'] and grant['expires_at'] > engine.clock(), 'Use a live grant.')
        require(db.execute('SELECT 1 FROM worker_runs WHERE run_id=?', (run_id,)).fetchone() is None, 'Run ID already exists; inspect its outcome instead of replaying it.')
        require(db.execute("SELECT 1 FROM worker_runs WHERE context_id=? AND state='running'", (context_id,)).fetchone() is None, 'Context already has a running worker; reconcile it before restarting.')
        for index in range(len(plan['steps'])):
            require(db.execute('SELECT 1 FROM actions WHERE request_id=?',(f'{run_id}.{index}',)).fetchone() is None,'Run request identifiers already exist; choose a new run ID.')
        db.execute('INSERT INTO worker_runs VALUES(?,?,?,?,?)', (run_id, context_id, sha(plan), 'running', canonical({'steps': []})))
        engine._event(db, 'worker_started', run_id, {'context_id': context_id, 'plan_sha256': sha(plan), 'timeout_seconds': timeout})
        principal, task_id, grant_id = grant['principal'], grant['task_id'], grant['grant_id']
    process = None
    results = []
    state = 'failed'
    error_code = None
    try:
        with tempfile.TemporaryDirectory(prefix='decisionguard-worker-') as directory:
            process = subprocess.Popen([sys.executable, '-I', '-S', str(Path(__file__).with_name('worker_process.py')), str(timeout)],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                       cwd=directory, env={}, close_fds=True, start_new_session=True, bufsize=0)
            channel = Channel(process, time.monotonic() + timeout)
            channel.write(plan)
            for index, step in enumerate(plan['steps']):
                message = channel.read()
                with engine.store.transaction() as db:
                    require(db.execute('SELECT state FROM worker_runs WHERE run_id=?',(run_id,)).fetchone()[0]=='running','Run has been stopped by the owner.')
                if step['kind'] == 'receive':
                    exact(message, {'kind', 'index', 'output_id'})
                    require(message['kind'] == 'receive' and type(message['index']) is int and message['index'] == index and message['output_id'] == step['output_id'], 'Invalid receive proposal.')
                    delivered = engine.consume(context_id, message['output_id'])
                    result = {'status': 'completed' if 'output' in delivered else 'cancelled',
                              'output': delivered.get('output'), 'output_id': message['output_id']}
                else:
                    action = proposal_action(message, step, index, run_id, task_id, grant_id)
                    engine.submit(action, principal=principal)
                    result = engine.dispatch(action.request_id, principal=principal)
                results.append({k: v for k, v in result.items() if k != 'output'})
                with engine.store.transaction() as db:
                    db.execute('UPDATE worker_runs SET body=? WHERE run_id=?', (canonical({'steps': results}), run_id))
                if result['status'] != 'completed':
                    state = 'blocked'
                    break
                if step['kind'] in ('read', 'receive'):
                    require(isinstance(result.get('output'), dict) and isinstance(result['output'].get('content'), str), 'Only text-bearing outputs can feed this worker.')
                channel.write({'status': 'completed', 'output': result['output']})
            else:
                message = channel.read()
                exact(message, {'kind', 'steps'})
                require(message['kind'] == 'done' and type(message['steps']) is int and message['steps'] == len(plan['steps']), 'Worker finished with an invalid step count.')
                process.wait(timeout=max(0.01, channel.deadline - time.monotonic()))
                require(process.returncode == 0, 'Worker exited unsuccessfully.')
                state = 'completed'
    except (GuardError, OSError, subprocess.TimeoutExpired) as error:
        error_code = error.code if isinstance(error, GuardError) else 'worker_failure'
    finally:
        if process is not None:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait()
            process.stdin.close(); process.stdout.close()
        # A crash after a tool commit never erases its receipt. Owner can reconcile.
        with engine.store.transaction() as db:
            recorded=db.execute('SELECT state FROM worker_runs WHERE run_id=?',(run_id,)).fetchone()[0]
            if recorded=='stopped':
                state='stopped'
            report = {'run_id': run_id, 'context_id': context_id, 'state': state, 'error': error_code,
                      'steps': results, 'worker_type': 'local-deterministic-text-statistics'}
            db.execute('UPDATE worker_runs SET state=?,body=? WHERE run_id=?', (state, canonical(report), run_id))
            engine._event(db, 'worker_finished', run_id, {'state': state, 'error': error_code})
    return report


def worker_status(engine, run_id):
    identifier(run_id)
    with engine.store.transaction() as db:
        row = db.execute('SELECT * FROM worker_runs WHERE run_id=?', (run_id,)).fetchone()
        require(row is not None, 'Unknown run.')
        return {'run_id': run_id, 'context_id': row['context_id'], 'state': row['state'],
                'plan_sha256': row['plan_digest'], 'report': json.loads(row['body'])}


def stop_worker(engine, run_id, reason):
    identifier(run_id)
    require(isinstance(reason,str) and 0<len(reason)<=500,'Supply a stop/recovery reason.')
    with engine.store.transaction() as db:
        row=db.execute('SELECT * FROM worker_runs WHERE run_id=?',(run_id,)).fetchone()
        require(row is not None and row['state']=='running','Only a running or interrupted run needs stopping.')
        containment=engine._quarantine(db,row['context_id'],'worker_stop: '+reason)
        db.execute("UPDATE worker_runs SET state='stopped' WHERE run_id=?",(run_id,))
        engine._event(db,'worker_stopped',run_id,{'reason':reason})
        return {'run_id':run_id,'state':'stopped','containment':containment,
                'note':'Authority revoked. An active worker exits on its next broker exchange or deadline; inspect receipts for already committed effects.'}


def read_note(engine, request_id):
    """Owner forensic view, never an untrusted-worker endpoint."""
    identifier(request_id)
    with engine.store.transaction() as db:
        row=db.execute('SELECT * FROM notes WHERE request_id=?',(request_id,)).fetchone()
        require(row is not None,'No completed note exists for that request.')
        return dict(row)
