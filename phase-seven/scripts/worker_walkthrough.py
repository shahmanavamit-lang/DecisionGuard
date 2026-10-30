"""Run actual isolated local worker processes over a user-supplied text file."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from decisionguard.broker import run_worker,read_note
from decisionguard.contracts import GuardError,Permission,Scope
from decisionguard.engine import Engine
from decisionguard.storage import Store


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--workspace',type=Path,required=True)
    args=parser.parse_args()
    try:
        args.workspace.mkdir(mode=0o700,parents=True,exist_ok=False)
        db=args.workspace/'state.sqlite3';Store.initialize(db);engine=Engine(db)
        resource=engine.import_file('input',args.input)
        engine.label('input',1,'document',2)
        engine.approve(Scope('review','Local file statistics',(Permission('read_file','input',1),Permission('write_note','input',1)),
                             10,10*resource['bytes']+10000),reason='Owner approves the bounded local worker exercise')
        engine.manage('review')
        for name in ('analyst','probe'):
            engine.grant(name,name,'review',ttl=3600)
            engine.open_context(name,name,name+'-memory')
        plan={'steps':[{'kind':'read','resource_id':'input','resource_version':1},
                       {'kind':'summarize','resource_id':'input','resource_version':1,'source':0}]}
        (args.workspace/'plan.json').write_text(json.dumps(plan,indent=2))
        normal=run_worker(engine,'analyst','analysis',plan)
        require_note=normal['state']=='completed'
        summary=json.loads(read_note(engine,'analysis.1')['content']) if require_note else None
        blocked=run_worker(engine,'probe','unauthorized',{'steps':[{'kind':'read','resource_id':'outside-task','resource_version':1}]})
        report={'mode':'local_deterministic_worker_processes','normal':normal,'computed_summary':summary,
                'unauthorized':blocked,'receipt_count':engine.inspect()['receipt_count'],
                'note':'No LLM or semantic prompt-injection detector is involved.'}
        (args.workspace/'report.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2));return 0 if require_note and blocked['state']=='blocked' else 2
    except (GuardError,OSError,UnicodeError) as error:
        print(json.dumps({'error':str(error)}),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
