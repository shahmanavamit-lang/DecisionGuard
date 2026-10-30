"""Compare independent and dependent branches using a user-provided local file."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from decisionguard.contracts import Action, GuardError, Permission, Scope
from decisionguard.engine import Engine
from decisionguard.storage import Store


def scenario(folder,source,dependent):
    folder.mkdir(mode=0o700);db=folder/'state.sqlite3';Store.initialize(db);engine=Engine(db)
    data=engine.import_file('input',source)
    engine.label('input',1,'document',2)
    engine.approve(Scope('review','Two managed local branches',(Permission('read_file','input',1),),20,20*data['bytes']),reason='Owner approves the exercise')
    engine.manage('review')
    for name in ('supplier','inventory'):
        engine.grant(name,name,'review',ttl=3600)
        engine.open_context(name,name,name+'-memory')
    first=Action('supplier-read','review','supplier','read_file','input',1)
    engine.submit(first,principal='supplier');engine.dispatch(first.request_id,principal='supplier')
    if dependent:engine.consume('inventory','supplier-read')
    next_action=replace(first,request_id='inventory-read',grant_id='inventory')
    engine.submit(next_action,principal='inventory')
    # Propose a non-permitted operation; there is no corresponding protected effect.
    violation=replace(first,request_id='supplier-violation',operation='write_note',content='An unauthorized proposed operation')
    denied=engine.submit(violation,principal='supplier')
    checked=engine.continuation('inventory-read')
    result=engine.dispatch('inventory-read',principal='inventory')
    return {'dependent':dependent,'violation_status':denied['status'],
            'continuation_check':checked,'inventory_status':result['status'],
            'receipt_count':engine.inspect()['receipt_count'],'graph':engine.graph(),
            'events':[e for e in engine.events() if e['kind'] in ('contexts_contained','continuation_allowed')]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--workspace',type=Path,required=True)
    args=parser.parse_args()
    try:
        args.workspace.mkdir(mode=0o700,parents=True,exist_ok=False)
        report={'mode':'scripted_local_runtime','independent':scenario(args.workspace/'independent',args.input,False),
                'dependent':scenario(args.workspace/'dependent',args.input,True)}
        (args.workspace/'report.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2));return 0
    except (GuardError,OSError,UnicodeError) as error:
        print(json.dumps({'error':str(error)}),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
