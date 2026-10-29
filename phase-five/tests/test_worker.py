from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
from test_engine import Environment, ROOT
from decisionguard.broker import run_worker, validate_plan, worker_status, proposal_action
from decisionguard.contracts import GuardError
from decisionguard.engine import Engine


class WorkerTests(Environment):
    def setUp(self):
        super().setUp()
        self.engine.manage('review')
        self.engine.open_context('worker-context','grant','worker-memory')
        self.plan={'steps':[{'kind':'read','resource_id':'input','resource_version':1},
                            {'kind':'summarize','resource_id':'input','resource_version':1,'source':0}]}

    def test_real_process_computes_file_statistics(self):
        result=run_worker(self.engine,'worker-context','run',self.plan)
        self.assertEqual(result['state'],'completed',result)
        note=json.loads(self.sql("SELECT content FROM notes WHERE request_id='run.1'")[0][0])
        self.assertEqual(note['characters'],len(self.content))
        self.assertEqual(note['utf8_bytes'],len(self.content.encode()))
        self.assertEqual(note['words'],len(self.content.split()))
        self.assertEqual(self.engine.inspect()['receipt_count'],2)
        self.assertEqual(worker_status(Engine(self.db),'run')['state'],'completed')
        self.assertTrue(any(e['kind']=='continuation_allowed' for e in self.engine.events()))

    def test_out_of_scope_proposal_is_denied_and_contained(self):
        plan={'steps':[{'kind':'read','resource_id':'restricted','resource_version':1}]}
        result=run_worker(self.engine,'worker-context','bad',plan)
        self.assertEqual(result['state'],'blocked')
        self.assertEqual(result['steps'][0]['reason'],'outside_scope')
        self.assertEqual(self.engine.inspect()['receipt_count'],0)
        self.assertEqual(self.engine.graph()['contexts'][0]['quarantined'],1)

    def test_worker_has_no_direct_file_network_or_shell_capability(self):
        process=subprocess.run([sys.executable,'-I','-S',str(ROOT/'src/decisionguard/worker_process.py'),'5',str(self.db)],
                               cwd=self.root,env={},close_fds=True,capture_output=True,text=True,timeout=10)
        self.assertEqual(process.returncode,0,process.stderr)
        report=json.loads(process.stdout)
        self.assertEqual(report['blocked'],{'file':True,'network':True,'shell':True})
        self.assertFalse(any('KEY' in k or 'TOKEN' in k for k in report['environment_keys']))

    def test_environment_secrets_not_passed(self):
        with patch.dict(os.environ,{'DECISIONGUARD_TEST_SECRET':'never pass this'}):
            real=subprocess.Popen
            seen=[]
            def spy(*args,**kwargs):
                seen.append(kwargs)
                return real(*args,**kwargs)
            with patch('decisionguard.broker.subprocess.Popen',side_effect=spy):
                self.assertEqual(run_worker(self.engine,'worker-context','env',self.plan)['state'],'completed')
            self.assertEqual(seen[0]['env'],{})
            self.assertTrue(seen[0]['close_fds'])
            self.assertNotEqual(Path(seen[0]['cwd']),self.db.parent)

    def test_plan_cannot_supply_authority_paths_or_code(self):
        for plan in ({'steps':self.plan['steps'],'db':'secret'},
                     {'steps':[{'kind':'python','code':'anything'}]},
                     {'steps':[{'kind':'read','resource_id':'input','resource_version':1,'grant_id':'grant'}]},
                     {'steps':[{'kind':'read','resource_id':'../input','resource_version':1}]},
                     {'steps':[{'kind':'summarize','resource_id':'input','resource_version':1,'source':0}]}):
            with self.assertRaises(GuardError):validate_plan(plan)

    def test_protocol_cannot_change_authority_or_order(self):
        message={'kind':'action','index':0,'operation':'read_file','resource_id':'input','resource_version':1,'content':''}
        for changes in ({'grant_id':'other'},{'index':1},{'resource_id':'restricted'},{'operation':'write_note'}):
            with self.assertRaises(GuardError):proposal_action({**message,**changes},self.plan['steps'][0],0,'run','review','grant')

    def test_duplicate_run_rejected_without_duplicate_effect(self):
        run_worker(self.engine,'worker-context','run',self.plan)
        with self.assertRaises(GuardError):run_worker(self.engine,'worker-context','run',self.plan)
        self.assertEqual(self.engine.inspect()['note_count'],1)

    def test_preexisting_request_id_cannot_be_replayed_into_worker(self):
        self.execute(self.action('collision.0'))
        with self.assertRaises(GuardError):run_worker(self.engine,'worker-context','collision',self.plan)

    def test_unmanaged_missing_or_quarantined_context_rejected(self):
        with self.assertRaises(GuardError):run_worker(self.engine,'missing','run',self.plan)
        self.engine.contain('worker-context','Owner incident')
        with self.assertRaises(GuardError):run_worker(self.engine,'worker-context','run',self.plan)

    def test_timeout_kills_worker_without_effect(self):
        from decisionguard.broker import Channel
        with patch.object(Channel,'read',side_effect=GuardError('worker_timeout','Test deadline')):
            result=run_worker(self.engine,'worker-context','timeout',self.plan)
        self.assertEqual(result['state'],'failed')
        self.assertEqual(result['error'],'worker_timeout')
        self.assertEqual(self.engine.inspect()['receipt_count'],0)

    def test_failure_after_effect_preserves_receipt(self):
        from decisionguard.broker import Channel
        original=Channel.write
        calls=[]
        def fail_second(channel,data):
            calls.append(data)
            if len(calls)==2:raise BrokenPipeError('lost response')
            return original(channel,data)
        with patch.object(Channel,'write',new=fail_second):
            result=run_worker(self.engine,'worker-context','lost',self.plan)
        self.assertEqual(result['state'],'failed')
        self.assertEqual(self.engine.reconcile('lost.0')['status'],'completed')
        self.assertEqual(self.engine.inspect()['note_count'],0)

    def test_receive_uses_checked_delivery_and_records_lineage(self):
        self.execute(self.action('source'))
        self.engine.grant('receiver','receiver','review',ttl=100)
        self.engine.open_context('receiver','receiver','receiver-memory')
        plan={'steps':[{'kind':'receive','output_id':'source'},
                       {'kind':'summarize','resource_id':'input','resource_version':1,'source':0}]}
        result=run_worker(self.engine,'receiver','receive',plan)
        self.assertEqual(result['state'],'completed',result)
        self.engine.contain('worker-context','Incident')
        self.assertTrue(all(c['quarantined'] for c in self.engine.graph()['contexts']))

    def test_corrupt_worker_json_fails_without_effect(self):
        from decisionguard.broker import Channel
        with patch.object(Channel,'read',return_value={'kind':'action','approved':True}):
            result=run_worker(self.engine,'worker-context','invalid',self.plan)
        self.assertEqual(result['state'],'failed')
        self.assertEqual(self.engine.inspect()['receipt_count'],0)

    def test_run_budgets_rejected(self):
        for timeout in (0,-1,61,True,float('nan')):
            with self.assertRaises(GuardError):run_worker(self.engine,'worker-context','invalid',self.plan,timeout=timeout)

    def test_channel_real_deadline_and_frame_limit(self):
        import time
        from decisionguard.broker import Channel
        programs=[('import time;time.sleep(3)','worker_timeout'),
                  ('import sys;sys.stdout.write("x"*100);sys.stdout.flush()', 'invalid_input')]
        for code,expected in programs:
            process=subprocess.Popen([sys.executable,'-I','-S','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
            try:
                channel=Channel(process,time.monotonic()+(0.1 if expected=='worker_timeout' else 3))
                with patch('decisionguard.broker.MAX_FRAME',32),self.assertRaises(GuardError) as caught:
                    channel.read()
                self.assertEqual(caught.exception.code,expected)
            finally:
                process.kill();process.wait();process.stdin.close();process.stdout.close()

    def test_channel_duplicate_keys_rejected(self):
        import time
        from decisionguard.broker import Channel
        process=subprocess.Popen([sys.executable,'-I','-S','-c','print(\'{"kind":1,"kind":2}\')'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
        try:
            with self.assertRaises(GuardError):Channel(process,time.monotonic()+3).read()
        finally:
            process.wait();process.stdin.close();process.stdout.close()

    def test_behavior_hold_stops_worker_before_note_effect(self):
        from test_learning import LearningTests
        LearningTests.train(self)
        result=run_worker(self.engine,'worker-context','hold',self.plan)
        self.assertEqual(result['state'],'blocked')
        self.assertEqual(result['steps'][-1]['status'],'held')
        self.assertEqual(self.engine.inspect()['note_count'],0)

    def test_stop_during_run_revokes_authority(self):
        from decisionguard.broker import Channel,stop_worker
        original=Channel.read
        calls=[]
        def stop_before_request(channel):
            message=original(channel)
            if not calls:
                stop_worker(self.engine,'stop','Owner cancelled')
                calls.append(True)
            return message
        with patch.object(Channel,'read',new=stop_before_request):
            result=run_worker(self.engine,'worker-context','stop',self.plan)
        self.assertEqual(result['state'],'stopped')
        self.assertEqual(self.engine.inspect()['receipt_count'],0)
        self.assertEqual(worker_status(self.engine,'stop')['state'],'stopped')

    def test_interrupted_run_is_explicitly_recovered_without_replay(self):
        from decisionguard.broker import stop_worker
        self.sql("INSERT INTO worker_runs VALUES('interrupted','worker-context','digest','running','{}')")
        with self.assertRaises(GuardError):run_worker(self.engine,'worker-context','new',self.plan)
        stop_worker(self.engine,'interrupted','Broker previously crashed')
        self.assertEqual(worker_status(self.engine,'interrupted')['state'],'stopped')
        self.assertEqual(self.engine.graph()['contexts'][0]['quarantined'],1)
