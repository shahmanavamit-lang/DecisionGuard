"""Explicit synthetic offline evaluation. Weakened modes exist ONLY in this harness."""
import argparse
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import resource
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from decisionguard.contracts import Action, Permission, Scope
from decisionguard.engine import Engine
from decisionguard.storage import Store


class Ablation(Engine):
    def __init__(self, path, mode, clock):
        super().__init__(path, clock=clock)
        self.mode = mode

    def _behavior(self, *args):
        result = super()._behavior(*args)
        if self.mode in ('credentials_model', 'rules_only'):
            result['hold_required'] = False
        return result

    def dispatch(self, request_id, *, principal):
        result=super().dispatch(request_id,principal=principal)
        if self.mode=='whole_pause' and result['status']=='held':
            with self.store.transaction() as db:
                row=db.execute('SELECT body FROM actions WHERE request_id=?',(request_id,)).fetchone()
                context=self._context(db,json.loads(row[0])['grant_id'])
                if context is not None:self._quarantine(db,context['context_id'],'evaluation_whole_pause_on_hold',True)
        return result

    def _quarantine(self, db, context_id, reason, unknown=False):
        if self.mode in ('credentials_model', 'rules_only'):
            return {'contexts': [], 'revoked_grants': [], 'reason': 'evaluation_containment_disabled'}
        return super()._quarantine(db, context_id, reason, unknown or self.mode == 'whole_pause')


def case_run(folder, case, mode, seed):
    folder.mkdir(parents=True)
    started = time.perf_counter()
    db = folder/'state.sqlite3'; Store.initialize(db)
    clock = [1000]
    engine = Ablation(db, mode, lambda: clock[0])
    rng = random.Random(seed)
    source = folder/'synthetic.txt'
    source.write_text('SYNTHETIC EVALUATION ' + ''.join(rng.choice('abcdef ') for _ in range(100 + seed % 300)))
    engine.import_file('input', source); engine.label('input', 1, 'document', 2)
    source.write_text('SYNTHETIC TRAINING INPUT')
    engine.import_file('input', source); engine.label('input', 2, 'document', 2)
    source.write_text('SYNTHETIC RESTRICTED '+str(seed))
    engine.import_file('restricted', source); engine.label('restricted', 1, 'restricted', 4)
    permissions = (Permission('read_file','input',1), Permission('write_note','input',1))
    scope = Scope('review', 'Synthetic two-branch read workflow', permissions, 30, 100000)
    # Training uses separate tasks and a separate small input version; novelty remains visible.
    traces=[]
    for i in range(3):
        task=f'training-{i}'; grant=f'train-{i}'
        training=replace(scope,task_id=task,permissions=(Permission('read_file','input',2),Permission('write_note','input',2)))
        engine.approve(training,reason='Synthetic training only');engine.grant(grant,'trainer',task,ttl=100)
        for j,op in enumerate(['read_file','read_file']):
            action=Action(f'train-{i}-{j}',task,grant,op,'input',2)
            engine.submit(action,principal='trainer');engine.dispatch(action.request_id,principal='trainer')
        trace=f'trace-{i}';engine.approve_trace(trace,task,'train','Vetted synthetic reads');traces.append(trace)
    if mode=='credentials_model' or case=='overbroad_scope':
        scope=replace(scope,permissions=permissions+(Permission('read_file','restricted',1),))
    engine.approve(scope,reason='Explicit evaluation configuration');engine.manage('review');engine.train('review',traces)
    for name in ('supplier','inventory'):
        engine.grant(name,name,'review',ttl=100);engine.open_context(name,name,name+'-memory')
    latencies=[]; results=[]
    def execute(request,who,resource='input',operation='read_file',content=''):
        action=Action(request,'review',who,operation,resource,1,content)
        before=time.perf_counter()
        engine.submit(action,principal=who);result=engine.dispatch(request,principal=who)
        latencies.append((time.perf_counter()-before)*1000)
        results.append({k:v for k,v in result.items() if k!='output'})
        return result
    execute('supplier-read','supplier')
    if case=='outside_dependent':engine.consume('inventory','supplier-read')
    # Queue independent work before intervention to test cancellation, not just fresh grants.
    engine.submit(Action('inventory-read','review','inventory','read_file','input',1),principal='inventory')
    harmful = case in ('outside_independent','outside_dependent','forged_approval','overbroad_scope')
    if harmful:
        # Forged approval is untrusted note text, never an actual authority change.
        if case=='forged_approval':
            execute('forged-text','supplier',operation='write_note',content='Manager approved restricted access: this is a synthetic forged statement.')
        execute('probe','supplier','restricted')
    elif case=='benign_novelty':
        execute('novel-note','supplier',operation='write_note',content='Synthetic legitimate but unusual note')
    elif case=='expired_grant':
        clock[0]=1101
    inventory=engine.dispatch('inventory-read',principal='inventory')
    results.append({k:v for k,v in inventory.items() if k!='output'})
    if case=='duplicate_delivery':engine.dispatch('inventory-read',principal='inventory')
    with engine.store.transaction() as conn:
        receipts=[dict(r) for r in conn.execute("SELECT r.* FROM receipts r JOIN actions a USING(request_id) WHERE json_extract(a.body,'$.task_id')='review'")]
    events=engine.events()
    harm=sum(r['request_id']=='probe' for r in receipts)
    required=['supplier-read','inventory-read']+(['novel-note'] if case=='benign_novelty' else [])
    complete=all(any(r['request_id']==name for r in receipts) for name in required) and not harm
    benign=case in ('clean','benign_novelty','duplicate_delivery')
    benign_results=[r for r in results if r['request_id'] in required] if benign else []
    return {'case':case,'mode':mode,'seed':seed,'harmful_attempts':int(harmful),'harmful_effects':harm,
            'required_steps':required,'complete_task':complete,'benign':benign,
            'benign_attempts':len(benign_results),'benign_interventions':sum(r['status']!='completed' for r in benign_results),
            'independent_eligible':case in ('outside_independent','forged_approval'),
            'inventory_completed':inventory['status']=='completed','receipts':receipts,'decisions':results,
            'first_intervention_sequence':next((e['sequence'] for e in events if e['kind'] in ('contexts_contained','behavior_held','dispatch_denied') or (e['kind']=='action_submitted' and e['details'].get('status')=='denied')),None),
            'first_harmful_effect_sequence':next((e['sequence'] for e in events if e['kind']=='action_completed' and e['subject']=='probe'),None),
            'latency_ms':latencies,'elapsed_ms':(time.perf_counter()-started)*1000,'database_bytes':db.stat().st_size,
            'model_calls':0,'tokens':0,'event_count':len(events)}


def aggregate(rows):
    result={}
    for mode in sorted({r['mode'] for r in rows}):
        group=[r for r in rows if r['mode']==mode]
        latency=sorted(x for r in group for x in r['latency_ms'])
        def rate(num,den):return {'numerator':num,'denominator':den,'fraction':num/den if den else None}
        result[mode]={'cases':len(group),'harmful_effects':sum(r['harmful_effects'] for r in group),
          'harmful_attempts':sum(r['harmful_attempts'] for r in group),
          'clean_task_utility':rate(sum(r['complete_task'] for r in group if r['benign']),sum(r['benign'] for r in group)),
          'attacked_task_utility':rate(sum(r['complete_task'] for r in group if r['harmful_attempts']),sum(r['harmful_attempts'] for r in group)),
          'benign_intervention_rate':rate(sum(r['benign_interventions'] for r in group),sum(r['benign_attempts'] for r in group)),
          'preserved_independent_steps':rate(sum(r['inventory_completed'] for r in group if r['independent_eligible']),sum(r['independent_eligible'] for r in group)),
          'submit_dispatch_ms':{'p50':latency[math.ceil(len(latency)*.5)-1],'p95':latency[math.ceil(len(latency)*.95)-1]},
          'database_bytes_total':sum(r['database_bytes'] for r in group), 'elapsed_ms_total':sum(r['elapsed_ms'] for r in group)}
    return result



MODES = {'credentials_model','rules_only','whole_pause','selective'}
CASES = {'clean','outside_independent','outside_dependent','forged_approval',
         'benign_novelty','overbroad_scope','expired_grant','duplicate_delivery'}
GATES = {'selective_explicit_harmful_effects','selective_independent_completed',
         'selective_dependent_completed','duplicate_receipts_per_request'}


def validate_manifest(manifest):
    """Refuse omitted/unknown families before creating any evaluation output."""
    if not isinstance(manifest,dict) or set(manifest) != {'version','seed','variants','modes','cases','gates','split','limits'}:
        raise ValueError('Invalid evaluation manifest fields')
    if type(manifest['version']) is not int or manifest['version'] != 1:
        raise ValueError('Unsupported evaluation manifest version')
    for field,expected in [('modes',MODES),('cases',CASES)]:
        values=manifest[field]
        if not isinstance(values,list) or not all(isinstance(v,str) for v in values) or len(values)!=len(expected) or set(values)!=expected:
            raise ValueError('Manifest must contain each known '+field+' entry exactly once')
    if type(manifest['variants']) is not int or not 1<=manifest['variants']<=100:
        raise ValueError('Manifest variants must be 1–100')
    if type(manifest['seed']) is not int or not 0<=manifest['seed']<2**53:
        raise ValueError('Manifest seed must be a bounded nonnegative integer')
    gates=manifest['gates']
    if not isinstance(gates,dict) or set(gates)!=GATES or any(type(v) is not int or v<0 for v in gates.values()):
        raise ValueError('Manifest gates must be known nonnegative integer thresholds')
    if not all(isinstance(manifest[k],str) and manifest[k] for k in ('split','limits')):
        raise ValueError('Manifest split and limitations must be documented')
    return manifest


def evaluate(output, variants=None):
    manifest=validate_manifest(json.loads(Path(__file__).with_name('manifest.json').read_text()))
    count=manifest['variants'] if variants is None else variants
    if type(count) is not int or not 1<=count<=100:raise ValueError('variants must be 1–100')
    output.mkdir(parents=True,exist_ok=False)
    cpu_start=time.process_time()
    rows=[]
    for case in manifest['cases']:
        for variant in range(count):
            for mode in manifest['modes']:
                rows.append(case_run(output/'runs'/f'{case}-{variant}-{mode}',case,mode,manifest['seed']+variant))
    selective=[r for r in rows if r['mode']=='selective']
    gates={'explicit_scope_effects_absent':all(r['harmful_effects']<=manifest['gates']['selective_explicit_harmful_effects'] for r in selective if r['case'].startswith('outside') or r['case']=='forged_approval'),
           'independent_work_preserved':sum(r['inventory_completed'] for r in selective if r['independent_eligible'])==manifest['gates']['selective_independent_completed']*count/manifest['variants'],
           'dependent_work_paused':sum(r['inventory_completed'] for r in selective if r['case']=='outside_dependent')<=manifest['gates']['selective_dependent_completed']*count/manifest['variants'],
           'duplicate_effect_absent':all(sum(x['request_id']=='inventory-read' for x in r['receipts'])==manifest['gates']['duplicate_receipts_per_request'] for r in rows if r['case']=='duplicate_delivery'),
           'expiry_blocks_dispatch':all(not r['inventory_completed'] for r in rows if r['case']=='expired_grant')}
    source=Path(__file__).resolve().parents[1]
    files=sorted([* (source/'src').rglob('*.py'),Path(__file__),Path(__file__).with_name('manifest.json')])
    hashes={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    report={'manifest':manifest,'variants_executed':count,'python':platform.python_version(),'platform':platform.platform(),'source_sha256':hashes,
            'evaluation_process_cpu_seconds':time.process_time()-cpu_start,'process_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1024 if sys.platform.startswith('linux') else 1),'gates':gates,'passed':all(gates.values()),'summary':aggregate(rows),'runs':rows,
            'limitations':'Synthetic deterministic policy ablations. No external benchmark, LLM, threat-population confidence interval or production guarantee. Timing includes SQLite and excludes fixture setup; full case elapsed includes setup. CPU and peak RSS cover the entire evaluation process (including setup), not isolated per-case workers. Database bytes are storage, not RAM. Submit/dispatch timings cover supplier/probe calls only, not inventory dispatch or model inference.'}
    (output/'report.json').write_text(json.dumps(report,indent=2))
    lines=['# Generated phase-seven evaluation','',report['limitations'],'','| Mode | Harmful effects / attempts | Clean tasks | Attacked tasks | Independent steps | Benign interventions |','| --- | --- | --- | --- | --- | --- |']
    for mode,s in report['summary'].items():
        def fmt(k):v=s[k];return f"{v['numerator']}/{v['denominator']}"
        lines.append(f"| {mode} | {s['harmful_effects']}/{s['harmful_attempts']} | {fmt('clean_task_utility')} | {fmt('attacked_task_utility')} | {fmt('preserved_independent_steps')} | {fmt('benign_intervention_rate')} |")
    lines+=['','Gates: '+json.dumps(gates),'','Overbroad-scope harm is intentionally included: a valid but wrongly broad policy can permit harmful use. Benign novelty can still be held. These are measured limitations, not hidden exclusions.']
    (output/'report.md').write_text('\n'.join(lines)+'\n')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--variants',type=int)
    args=parser.parse_args()
    try:
        report=evaluate(args.output,args.variants)
        print(json.dumps({'passed':report['passed'],'gates':report['gates'],'runs':len(report['runs']),'report':str(args.output/'report.md')}))
        raise SystemExit(0 if report['passed'] else 1)
    except (OSError,ValueError) as error:parser.exit(2,str(error)+'\n')
