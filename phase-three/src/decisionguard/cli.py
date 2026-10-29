"""Offline owner CLI; no tokens, network client or model provider."""
import argparse
import json
from pathlib import Path
import sys
from .contracts import Action, GuardError, Scope, read_json
from .engine import Engine
from .storage import Store


def main(argv=None):
    parser = argparse.ArgumentParser(description="DecisionGuard phase three: local durable action control")
    parser.add_argument('--db', type=Path, required=True, help='Local SQLite database file')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('init', help='Create an empty database owned by this OS user')
    imp = commands.add_parser('import-file', help='Import an immutable UTF-8 file snapshot')
    imp.add_argument('resource_id')
    imp.add_argument('file', type=Path)
    approve = commands.add_parser('approve', help='Owner approves a versioned task scope')
    approve.add_argument('scope', type=Path)
    approve.add_argument('--reason', required=True)
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
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            Store.initialize(args.db)
            result = {'status': 'initialized', 'schema_version': 2}
        else:
            engine = Engine(args.db)
            if args.command == 'label':
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
                result = engine.approve(Scope.from_dict(read_json(args.scope)), reason=args.reason)
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
        return 3 if isinstance(result, dict) and result.get('status') in ('denied', 'cancelled', 'held') else 0
    except GuardError as error:
        print(json.dumps({'error': error.code, 'message': str(error)}), file=sys.stderr)
        return 2
    except (OSError, ValueError) as error:
        print(json.dumps({'error': 'invalid_input', 'message': str(error)}), file=sys.stderr)
        return 2
