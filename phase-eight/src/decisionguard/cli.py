"""Offline owner CLI; no tokens, network client or model provider."""
import argparse
import json
from pathlib import Path
import sys
from .contracts import Action, GuardError, Scope, read_json
from .engine import Engine
from .storage import Store


def main(argv=None):
    parser = argparse.ArgumentParser(description="DecisionGuard phase seven: local durable action control")
    parser.add_argument('--db', type=Path, required=True, help='Local SQLite database file')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('init', help='Create an empty database owned by this OS user')
    imp = commands.add_parser('import-file', help='Import an immutable UTF-8 file snapshot')
    imp.add_argument('resource_id')
    imp.add_argument('file', type=Path)
    approve = commands.add_parser('approve', help='Owner approves a versioned task scope')
    approve.add_argument('scope', type=Path)
    approve.add_argument('--reason', required=True)
    approve.add_argument('--expected-version',type=int,help='Reject an approval if the current version changed; 0 means a new task')
    grant = commands.add_parser('grant', help='Owner assigns a task to a local runner identity')
    grant.add_argument('grant_id')
    grant.add_argument('--principal', required=True)
    grant.add_argument('--task', required=True)
    grant.add_argument('--ttl', type=int, required=True, help='Lifetime in seconds, up to one year')
    revoke = commands.add_parser('revoke')
    revoke.add_argument('grant_id')
    submit = commands.add_parser('submit', help='Queue a validated action without executing it')
    submit.add_argument('action', type=Path)
    submit.add_argument('--principal', required=True, help='Identity assigned by the trusted local runner')
    dispatch = commands.add_parser('dispatch', help='Recheck current authority and execute a queued action')
    dispatch.add_argument('request_id')
    dispatch.add_argument('--principal', required=True)
    reconcile = commands.add_parser('reconcile', help='Look up a prior outcome without re-execution')
    reconcile.add_argument('request_id')
    commands.add_parser('inspect', help='Owner view of state and stored results')
    commands.add_parser('events', help='Owner audit trail without resource bodies')
    label = commands.add_parser('label', help='Owner assigns immutable resource class and impact')
    label.add_argument('resource_id'); label.add_argument('--version',type=int,required=True)
    label.add_argument('--class',dest='resource_class',required=True); label.add_argument('--impact',type=int,required=True)
    trace = commands.add_parser('approve-trace', help='Freeze an owner-vetted benign task trace')
    trace.add_argument('trace_id'); trace.add_argument('--task',required=True)
    trace.add_argument('--split',choices=['train','validation','test'],required=True); trace.add_argument('--reason',required=True)
    train = commands.add_parser('train'); train.add_argument('task_id'); train.add_argument('--traces',nargs='+',required=True)
    evaluate = commands.add_parser('evaluate'); evaluate.add_argument('task_id'); evaluate.add_argument('--traces',nargs='+',required=True)
    review = commands.add_parser('review'); review.add_argument('request_id'); review.add_argument('--reason',required=True)
    manage = commands.add_parser('manage');manage.add_argument('task_id')
    context = commands.add_parser('context');context.add_argument('context_id');context.add_argument('--grant',required=True);context.add_argument('--memory',required=True)
    consume = commands.add_parser('consume');consume.add_argument('context_id');consume.add_argument('output_id')
    contain = commands.add_parser('contain');contain.add_argument('context_id');contain.add_argument('--reason',required=True);contain.add_argument('--unknown-lineage',action='store_true')
    continuation = commands.add_parser('continuation');continuation.add_argument('request_id')
    delegate = commands.add_parser('delegate');delegate.add_argument('parent');delegate.add_argument('child');delegate.add_argument('--principal',required=True);delegate.add_argument('--permissions',type=Path,required=True);delegate.add_argument('--ttl',type=int,required=True)
    commands.add_parser('graph')
    worker=commands.add_parser('run-worker',help='Run the fixed local worker through the authority broker')
    worker.add_argument('context_id');worker.add_argument('run_id');worker.add_argument('plan',type=Path)
    worker.add_argument('--timeout',type=float,default=10)
    status=commands.add_parser('worker-status');status.add_argument('run_id')
    note=commands.add_parser('note');note.add_argument('request_id')
    stop=commands.add_parser('stop-worker');stop.add_argument('run_id');stop.add_argument('--reason',required=True)
    fresh=commands.add_parser('start-fresh-worker',help='Owner-authorize a new context and run; never replay or reuse quarantined memory')
    fresh.add_argument('task_id');fresh.add_argument('run_id');fresh.add_argument('plan',type=Path)
    fresh.add_argument('--scope-version',type=int,required=True);fresh.add_argument('--reason',required=True)
    commands.add_parser('overview',help='Consistent bounded view of persisted runs, decisions and counts')
    console=commands.add_parser('console',help='Open the local HTML/CSS/JavaScript owner console')
    console.add_argument('--port',type=int,default=8765,help='Loopback port; 0 chooses a free port')
    args = parser.parse_args(argv)
    try:
        if args.command == 'console':
            from .console import serve
            serve(args.db,args.port)
            return 0
        if args.command == 'init':
            Store.initialize(args.db)
            result = {'status': 'initialized', 'schema_version': 4}
        else:
            engine = Engine(args.db)
            if args.command == 'start-fresh-worker':
                from .control import mutate
                result=mutate(engine,'start',{'task_id':args.task_id,'expected_version':args.scope_version,
                    'run_id':args.run_id,'plan':read_json(args.plan),'reason':args.reason})
            elif args.command == 'overview':
                from .control import snapshot
                result=snapshot(engine)
            elif args.command == 'run-worker':
                from .broker import run_worker
                result=run_worker(engine,args.context_id,args.run_id,read_json(args.plan),timeout=args.timeout)
            elif args.command == 'note':
                from .broker import read_note
                result=read_note(engine,args.request_id)
            elif args.command == 'stop-worker':
                from .broker import stop_worker
                result=stop_worker(engine,args.run_id,args.reason)
            elif args.command == 'worker-status':
                from .broker import worker_status
                result=worker_status(engine,args.run_id)
            elif args.command == 'manage':
                result=engine.manage(args.task_id)
            elif args.command == 'context':
                result=engine.open_context(args.context_id,args.grant,args.memory)
            elif args.command == 'consume':
                result=engine.consume(args.context_id,args.output_id)
            elif args.command == 'contain':
                result=engine.contain(args.context_id,args.reason,args.unknown_lineage)
            elif args.command == 'continuation':
                result=engine.continuation(args.request_id)
            elif args.command == 'delegate':
                result=engine.delegate(args.parent,args.child,args.principal,read_json(args.permissions),args.ttl)
            elif args.command == 'graph':
                result=engine.graph()
            elif args.command == 'label':
                result=engine.label(args.resource_id,args.version,args.resource_class,args.impact)
            elif args.command == 'approve-trace':
                result=engine.approve_trace(args.trace_id,args.task,args.split,args.reason)
            elif args.command == 'train':
                result=engine.train(args.task_id,args.traces)
            elif args.command == 'evaluate':
                result=engine.evaluate_profile(args.task_id,args.traces)
            elif args.command == 'review':
                result=engine.review(args.request_id,args.reason)
            elif args.command == 'import-file':
                result = engine.import_file(args.resource_id, args.file)
            elif args.command == 'approve':
                result = engine.approve(Scope.from_dict(read_json(args.scope)), reason=args.reason, expected_version=args.expected_version)
            elif args.command == 'grant':
                result = engine.grant(args.grant_id, args.principal, args.task, ttl=args.ttl)
            elif args.command == 'revoke':
                result = engine.revoke(args.grant_id)
            elif args.command == 'submit':
                result = engine.submit(Action.from_dict(read_json(args.action)), principal=args.principal)
            elif args.command == 'dispatch':
                result = engine.dispatch(args.request_id, principal=args.principal)
            elif args.command == 'reconcile':
                result = engine.reconcile(args.request_id)
            elif args.command == 'inspect':
                result = engine.inspect()
            else:
                result = engine.events()
        print(json.dumps(result, indent=2))
        if isinstance(result,dict) and result.get('state') in ('blocked','failed','stopped'):
            return 3 if result['state'] in ('blocked','stopped') else 2
        return 3 if isinstance(result, dict) and result.get('status') in ('denied', 'cancelled', 'held') else 0
    except GuardError as error:
        print(json.dumps({'error': error.code, 'message': str(error)}), file=sys.stderr)
        return 2
    except (OSError, ValueError) as error:
        print(json.dumps({'error': 'invalid_input', 'message': str(error)}), file=sys.stderr)
        return 2
