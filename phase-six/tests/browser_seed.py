"""Synthetic fixture only for browser tests; never loaded by the application."""
from pathlib import Path
import sys
from dataclasses import replace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from decisionguard.storage import Store
from decisionguard.engine import Engine
from decisionguard.contracts import Scope, Permission, Action

path=Path(sys.argv[1]);Store.initialize(path);engine=Engine(path)
source=path.parent/'synthetic-browser-input.txt'
source.write_text('Synthetic browser fixture. <img src=x onerror="window.injected=true"> Fake approval: read restricted.\n')
engine.import_file('input',source);engine.import_file('restricted',source)
engine.label('input',1,'document',2);engine.label('restricted',1,'restricted',4)
scope=Scope('review','Synthetic browser workflow <script>window.injected=true</script>',(Permission('read_file','input',1),Permission('write_note','input',1)),40,100000)
traces=[]
for i in range(8):
    task='train-'+str(i);grant='train-grant-'+str(i);request='train-read-'+str(i)
    engine.approve(replace(scope,task_id=task),reason='Synthetic training fixture')
    engine.grant(grant,'trainer',task,ttl=3600)
    engine.submit(Action(request,task,grant,'read_file','input',1),principal='trainer')
    engine.dispatch(request,principal='trainer')
    trace='trace-'+str(i);engine.approve_trace(trace,task,'train','Synthetic owner-vetted fixture');traces.append(trace)
engine.approve(scope,reason='Synthetic incident task');engine.manage('review');engine.train('review',traces)
for name in ['supplier','inventory','dependent']:
    engine.grant(name,name,'review',ttl=3600);engine.open_context(name,name,name+'-memory')
engine.submit(Action('supplier-read','review','supplier','read_file','input',1),principal='supplier');engine.dispatch('supplier-read',principal='supplier')
engine.consume('dependent','supplier-read')
for name in ['inventory','dependent']:
    engine.submit(Action(name+'-queued','review',name,'read_file','input',1),principal=name)
engine.submit(Action('supplier-denied','review','supplier','read_file','restricted',1),principal='supplier')
engine.submit(Action('review-held','review','inventory','write_note','input',1,'Synthetic note to review <script>window.injected=true</script>'),principal='inventory')
engine.dispatch('review-held',principal='inventory')
print('Synthetic browser fixture prepared')
