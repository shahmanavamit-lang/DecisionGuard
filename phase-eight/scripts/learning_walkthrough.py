"""Demonstrate local learning using the operator's input and note files."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from decisionguard.contracts import Action, GuardError, Permission, Scope, MAX_FILE_BYTES, require
from decisionguard.engine import Engine
from decisionguard.storage import Store


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--note',type=Path,required=True)
    parser.add_argument('--workspace',type=Path,required=True)
    args=parser.parse_args()
    try:
        with args.note.open('rb') as stream:
            raw=stream.read(MAX_FILE_BYTES+1)
        require(0<len(raw)<=MAX_FILE_BYTES,'Note must contain 1 byte to 1 MiB.')
        note=raw.decode('utf-8')
        args.workspace.mkdir(parents=True,exist_ok=False,mode=0o700)
        db=args.workspace/'state.sqlite3'; Store.initialize(db); engine=Engine(db)
        resource=engine.import_file('input',args.input)
        engine.label('input',1,'document',2)
        scope=Scope('target','Local learning exercise',(Permission('read_file','input',1),Permission('write_note','input',1)),
                    10,10*(resource['bytes']+len(raw)))
        def task(task_id):
            engine.approve(replace(scope,task_id=task_id),reason='Explicit walkthrough scope')
            engine.grant(task_id+'-grant','worker',task_id,ttl=3600)
        def read(task_id):
            action=Action(task_id+'-read',task_id,task_id+'-grant','read_file','input',1)
            engine.submit(action,principal='worker')
            return engine.dispatch(action.request_id,principal='worker')
        ids=[]
        for i in range(8):
            name=f'train-{i}'; task(name); read(name)
            trace=f'trace-{i}';engine.approve_trace(trace,name,'train','Scripted benign read inspected for this exercise');ids.append(trace)
        task('target'); profile=engine.train('target',ids)
        task('heldout');read('heldout')
        engine.approve_trace('heldout','heldout','test','Separate benign task; not training input')
        evaluation=engine.evaluate_profile('target',['heldout'])
        action=Action('unusual-note','target','target-grant','write_note','input',1,note)
        engine.submit(action,principal='worker'); held=engine.dispatch(action.request_id,principal='worker')
        require(held['status']=='held','Walkthrough expected a review hold.')
        engine.review(action.request_id,'Owner permits this note for the exercise')
        completed=engine.dispatch(action.request_id,principal='worker')
        report={'mode':'scripted_local_learning_exercise','profile_version':profile['version'],
                'training_trace_count':profile['trace_count'],'dataset_sha256':profile['dataset_sha256'],
                'held_action':held,'reviewed_action':completed,'held_out_evaluation':evaluation,
                'limitation':'Eight repetitions of a controlled read demonstrate the pipeline, not detector accuracy.'}
        (args.workspace/'report.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2));return 0
    except (GuardError,OSError,UnicodeError) as error:
        print(json.dumps({'error':str(error)}),file=sys.stderr);return 2

if __name__=='__main__':
    raise SystemExit(main())
