"""Real loopback HTTP checks, persisted incident flows, and review regressions."""
from dataclasses import asdict, replace
from http.client import HTTPConnection
import json
import threading
import time
from unittest.mock import patch

from test_engine import Environment
from decisionguard.console import ConsoleServer
from decisionguard import control as service
from decisionguard.contracts import GuardError
from decisionguard.engine import Engine
from decisionguard.storage import Store


class ConsoleTests(Environment):
    def setUp(self):
        super().setUp()
        self.engine.manage('review')
        self.engine.open_context('supplier', 'grant', 'supplier-memory')
        self.server = ConsoleServer(self.engine, 0)
        thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval':0.01})
        thread.start()
        def close():
            self.server.shutdown(); self.server.server_close(); thread.join(5)
        self.addCleanup(close)
        self.cookie = ''; self.csrf = ''

    def request(self, path, data=None, *, method=None, headers=None, raw=None):
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=15)
        base = {'Origin':self.server.origin, 'Cookie':self.cookie, 'X-DG-CSRF':self.csrf}
        if data is not None or raw is not None:
            base['Content-Type'] = 'application/json'
        base.update(headers or {})
        body = raw if raw is not None else json.dumps(data) if data is not None else None
        try:
            conn.request(method or ('POST' if body is not None else 'GET'), path, body=body, headers=base)
            response = conn.getresponse(); payload = response.read()
            result = json.loads(payload) if response.getheader('Content-Type','').startswith('application/json') else payload.decode()
            return response.status, result, dict(response.getheaders())
        finally:
            conn.close()

    def login(self):
        status, data, headers = self.request('/api/login', {'code':self.server.login_code})
        self.assertEqual(status, 200, data)
        self.cookie = headers['Set-Cookie'].split(';')[0]
        self.csrf = data['csrf']
        return headers

    def post(self, op, data, expected=200):
        status, result, _ = self.request('/api/admin/'+op, data)
        self.assertEqual(status, expected, result)
        return result

    def new_run(self, name='console-run', resource='input'):
        return {'task_id':'review', 'expected_version':1, 'run_id':name,
                'plan':{'steps':[{'kind':'read','resource_id':resource,'resource_version':1}]},
                'reason':'Owner reviewed this explicit fresh run'}

    def test_no_data_without_login_and_static_assets_are_allowlisted(self):
        for path in ('/api/snapshot','/api/events','/api/graph?task=review','/api/action?id=req'):
            self.assertEqual(self.request(path)[0],401)
        status, html, headers = self.request('/')
        self.assertEqual(status,200); self.assertIn('Unlock console',html)
        self.assertIn("default-src 'none'",headers['Content-Security-Policy'])
        self.assertEqual(headers['Cache-Control'],'no-store')
        self.login()
        for path in ('/../state.sqlite3','/src/decisionguard/engine.py','/state.sqlite3','/%2e%2e/state.sqlite3'):
            self.assertEqual(self.request(path)[0],404)

    def test_host_origin_fetch_metadata_and_csrf_are_enforced(self):
        self.login(); payload={'context_id':'supplier','reason':'Forged','unknown_lineage':False}
        for headers in ({'Host':'evil.example'}, {'Origin':'http://evil.example'}, {'Origin':''},
                        {'X-DG-CSRF':''}, {'Sec-Fetch-Site':'cross-site'}, {'Sec-Fetch-Site':'same-site'}):
            self.assertEqual(self.request('/api/admin/contain',payload,headers=headers)[0],403)
        self.assertFalse(self.engine.graph()['contexts'][0]['quarantined'])

    def test_login_code_single_use_cookie_and_session_expiry(self):
        code=self.server.login_code; headers=self.login()
        self.assertIn('HttpOnly',headers['Set-Cookie']);self.assertIn('SameSite=Strict',headers['Set-Cookie'])
        self.assertEqual(self.request('/api/login',{'code':code})[0],401)
        self.assertEqual(self.request('/api/session')[0],200)
        with self.server.auth_lock:
            for session in self.server.sessions.values():session['expires']=time.monotonic()-1
        self.assertEqual(self.request('/api/snapshot')[0],401)

    def test_expired_login_and_attempt_limit(self):
        code=self.server.login_code
        self.server.login_expires=time.monotonic()-1
        self.assertEqual(self.request('/api/login',{'code':code})[0],401)
        self.server.login_expires=time.monotonic()+100
        self.server.failures=10
        self.assertEqual(self.request('/api/login',{'code':code})[0],401)

    def test_logout_revokes_session(self):
        self.login()
        self.assertEqual(self.request('/api/logout',{})[0],200)
        self.assertEqual(self.request('/api/snapshot')[0],401)

    def test_json_duplicate_nonfinite_and_wrong_type_rejected(self):
        self.login()
        for raw in ('{"reason":"a","reason":"b"}', '{"reason":NaN}', 'null','[]','{'):
            self.assertEqual(self.request('/api/admin/contain',raw=raw)[0],400)
        self.assertEqual(self.request('/api/admin/contain',{},headers={'Content-Type':'text/plain'})[0],400)
        self.assertEqual(self.request('/api/admin/contain',{},headers={'Transfer-Encoding':'chunked'})[0],400)

    def test_method_unknown_route_and_query_validation(self):
        self.login()
        self.assertEqual(self.request('/api/snapshot',method='DELETE')[0],501)
        self.assertEqual(self.request('/api/missing')[0],404)
        for query in ('before=-1','before=oops','before=1&before=2','other=2'):
            self.assertEqual(self.request('/api/events?'+query)[0],400)

    def test_snapshot_uses_real_receipts_and_omits_document_content(self):
        self.execute()
        self.execute(self.action('bad',resource_id='restricted'))
        self.login()
        status, data, _=self.request('/api/snapshot')
        self.assertEqual(status,200)
        self.assertEqual(data['counts']['receipts'],1)
        self.assertEqual(data['counts']['denied'],1)
        self.assertEqual(data['counts']['quarantined'],1)
        self.assertNotIn(self.content,json.dumps(data))
        status, detail, _=self.request('/api/action?id=req')
        self.assertEqual(detail['output']['content'],self.content)
        self.assertIsNotNone(detail['receipt'])

    def test_new_context_runs_real_worker_and_duplicate_has_no_effect(self):
        self.login(); result=self.post('start',self.new_run())
        self.assertEqual(result['state'],'completed')
        self.assertEqual(self.engine.reconcile('console-run.0')['output']['content'],self.content)
        self.post('start',self.new_run(),400)
        self.assertEqual(self.engine.inspect()['receipt_count'],1)
        self.assertTrue(any(e['kind']=='console_fresh_context' for e in self.engine.events()))

    def test_denial_contains_only_affected_context_and_independent_continues(self):
        self.login()
        bad=self.post('start',self.new_run('bad','restricted'))
        self.assertEqual(bad['state'],'blocked')
        self.assertIsNone(self.engine.reconcile('bad.0')['receipt'])
        self.assertEqual(self.post('start',self.new_run('independent'))['state'],'completed')
        self.assertEqual(self.engine.inspect()['receipt_count'],1)
        self.assertEqual(sum(c['quarantined'] for c in self.engine.graph()['contexts']),1)

    def test_owner_containment_propagates_shared_output(self):
        self.execute()
        self.engine.grant('inventory','inventory','review',ttl=100)
        self.engine.open_context('inventory','inventory','separate-memory')
        self.engine.consume('inventory','req')
        self.login()
        result=self.post('contain',{'context_id':'supplier','reason':'Confirmed incident','unknown_lineage':False})
        self.assertEqual(result['contexts'],['inventory','supplier'])
        status,graph,_=self.request('/api/graph?task=review')
        self.assertEqual(status,200);self.assertTrue(graph['edges'])
        self.assertTrue(any(n['node_id']=='o:req' and n['quarantined'] for n in graph['nodes']))

    def test_held_review_continuation_dispatch_and_replay(self):
        from test_learning import LearningTests
        LearningTests.train(self)
        self.execute(self.action('held',operation='write_note',content='<script>untrusted content</script>'))
        self.login()
        payload={'request_id':'held','reason':'Reviewed exact content'}
        self.assertFalse(self.post('continuation',payload)['eligible'])
        self.post('review',payload)
        check=self.post('continuation',payload)
        self.assertTrue(check['eligible']);self.assertTrue(check['review_valid'])
        self.assertEqual(self.post('dispatch',payload)['status'],'completed')
        self.assertEqual(self.post('dispatch',payload)['status'],'completed')
        self.assertEqual(self.engine.inspect()['note_count'],1)

    def test_new_profile_and_revocation_invalidate_review_preview(self):
        from test_learning import LearningTests
        traces=LearningTests.train(self)
        self.execute(self.action('held',operation='write_note',content='Owner-reviewed content'))
        self.engine.review('held','Initial review')
        self.assertTrue(self.engine.continuation('held')['eligible'])
        self.engine.train('review',traces)
        self.assertFalse(self.engine.continuation('held')['eligible'])
        self.engine.review('held','Updated review')
        self.engine.contain('supplier','Incident')
        self.assertFalse(self.engine.continuation('held')['eligible'])
        self.assertEqual(self.engine.inspect()['note_count'],0)

    def test_approval_has_atomic_stale_version_check(self):
        self.login(); data={'scope':asdict(self.scope),'expected_version':1,'reason':'Intentional updated scope'}
        self.assertEqual(self.post('approve',data)['scope_version'],2)
        self.post('approve',data,400)
        self.post('start',self.new_run(),400)
        self.assertEqual(self.engine.inspect()['tasks'][0]['current_version'],2)
        self.assertEqual(len(self.engine.graph()['contexts']),1)

    def test_unknown_fields_never_create_authority(self):
        self.login()
        for change in ({'principal':'attacker'},{'approved':True},{'db':'/tmp/other'}):
            self.post('start',{**self.new_run(),**change},400)
        self.assertEqual(self.engine.inspect()['receipt_count'],0)
        self.assertEqual(len(self.engine.graph()['contexts']),1)

    def test_stop_interrupted_run_and_fresh_restart_do_not_reuse_memory(self):
        self.sql("INSERT INTO worker_runs VALUES('interrupted','supplier','digest','running','{}')")
        self.login()
        self.post('stop',{'run_id':'interrupted','reason':'Reconciled an interrupted broker'})
        result=self.post('start',self.new_run('restart'))
        self.assertEqual(result['state'],'completed');self.assertNotEqual(result['context_id'],'supplier')
        self.assertEqual(next(c for c in self.engine.graph()['contexts'] if c['context_id']=='supplier')['quarantined'],1)

    def test_partial_snapshot_graph_and_event_pagination_are_explicit(self):
        self.execute();self.login()
        with patch.object(service,'LIMIT',2):
            data=self.request('/api/snapshot')[1]
            self.assertIn('resources',data)
            events=self.request('/api/events')[1]
            self.assertEqual(len(events['events']),2);self.assertIsNotNone(events['next_before'])
            next_events=self.request('/api/events?before='+str(events['next_before']))[1]
            self.assertLess(next_events['events'][0]['sequence'],events['events'][-1]['sequence'])
            self.assertTrue(self.request('/api/graph?task=review')[1]['partial'])

    def test_storage_failure_is_not_an_empty_healthy_dashboard(self):
        self.login()
        with patch.object(self.engine.store,'transaction',side_effect=GuardError('store_unavailable','Storage unavailable')):
            status,data,_=self.request('/api/snapshot')
        self.assertEqual(status,503);self.assertEqual(data['error'],'store_unavailable')

    def test_empty_store_and_phase_five_schema_are_supported(self):
        db=self.root/'empty.sqlite3';Store.initialize(db)
        view=service.snapshot(Engine(db))
        self.assertEqual(view['counts']['receipts'],0);self.assertEqual(view['runs'],[])
        self.assertEqual(view['truncated'],[])

    def test_ui_uses_text_nodes_and_no_external_assets(self):
        self.login()
        for path in ('/','/style.css','/app.js'):
            status,body,_=self.request(path);self.assertEqual(status,200)
            self.assertNotIn('https://',body)
        script=self.request('/app.js')[1]
        self.assertNotIn('innerHTML',script);self.assertNotIn('eval(',script)
        self.assertIn('textContent',script)
