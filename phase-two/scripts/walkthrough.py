"""Exercise phase two with three user-supplied files; no bundled business records."""
import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from decisionguard.contracts import Action, GuardError, MAX_FILE_BYTES, Permission, Scope, require
from decisionguard.engine import Engine
from decisionguard.storage import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='Your UTF-8 input file')
    parser.add_argument('--restricted', type=Path, required=True, help='A second UTF-8 file for the approval exercise')
    parser.add_argument('--note', type=Path, required=True, help='Your UTF-8 note text, stored as a local database effect')
    parser.add_argument('--workspace', type=Path, required=True, help='New directory for this walkthrough')
    args = parser.parse_args()
    try:
        with args.note.open('rb') as stream:
            note_bytes = stream.read(MAX_FILE_BYTES + 1)
        require(0 < len(note_bytes) <= MAX_FILE_BYTES, 'Note must contain 1 byte to 1 MiB.')
        note = note_bytes.decode('utf-8')
        args.workspace.mkdir(parents=True, mode=0o700, exist_ok=False)
        db = args.workspace/'state.sqlite3'
        Store.initialize(db)
        engine = Engine(db)
        source = engine.import_file('input', args.input)
        restricted = engine.import_file('restricted', args.restricted)
        scope = Scope('local-review', 'Review the operator-provided input file',
                      (Permission('read_file','input',1), Permission('write_note','input',1)),
                      10, 2 * source['bytes'] + restricted['bytes'] + len(note_bytes))
        (args.workspace/'scope-v1.json').write_text(json.dumps(asdict(scope), indent=2))
        engine.approve(scope, reason='Owner starts the local walkthrough')
        engine.grant('initial-grant','local-worker','local-review',ttl=3600)
        outcomes = []
        def run(action):
            (args.workspace/f'{action.request_id}.json').write_text(json.dumps(asdict(action), indent=2))
            engine.submit(action, principal='local-worker')
            result = engine.dispatch(action.request_id, principal='local-worker')
            outcomes.append({k:result[k] for k in ('request_id','status','reason','receipt')})
            return result
        base = Action('allowed-read','local-review','initial-grant','read_file','input',1)
        run(base)
        run(replace(base, request_id='blocked-read', resource_id='restricted'))
        note_action = replace(base, request_id='save-note', operation='write_note', content=note)
        first = run(note_action)
        restarted = Engine(db)
        retry = restarted.submit(note_action, principal='local-worker')
        require(first == retry, 'Unexpected change to a completed result after restart.')
        scope2 = replace(scope, permissions=scope.permissions + (Permission('read_file','restricted',1),))
        (args.workspace/'scope-v2.json').write_text(json.dumps(asdict(scope2), indent=2))
        engine.approve(scope2, reason='Owner explicitly authorizes the second file for this exercise')
        engine.grant('updated-grant','local-worker','local-review',ttl=3600)
        run(replace(base, request_id='approved-read', grant_id='updated-grant', resource_id='restricted'))
        pending = replace(base, request_id='revoked-read', grant_id='updated-grant')
        engine.submit(pending, principal='local-worker')
        engine.revoke('updated-grant')
        cancelled = engine.dispatch(pending.request_id, principal='local-worker')
        outcomes.append({k:cancelled[k] for k in ('request_id','status','reason','receipt')})
        state = engine.inspect()
        report = {'mode':'local_file_walkthrough', 'actions':outcomes,
                  'receipt_count':state['receipt_count'], 'note_count':state['note_count'],
                  'usage':state['tasks'], 'retry_returned_original_result':first == retry}
        (args.workspace/'report.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        return 0
    except (GuardError, OSError, UnicodeError) as error:
        print(json.dumps({'error':str(error)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
