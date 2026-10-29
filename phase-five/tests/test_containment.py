from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from test_engine import Environment
from decisionguard.contracts import GuardError, Permission
from decisionguard.engine import Engine


class ContainmentTests(Environment):
    def setUp(self):
        super().setUp()
        self.engine.manage('review')
        self.engine.open_context('supplier','grant','supplier-memory')
        self.engine.grant('inventory-grant','inventory','review',ttl=100)
        self.engine.open_context('inventory','inventory-grant','inventory-memory')

    def queue_inventory(self,name='stock'):
        action=self.action(name,grant_id='inventory-grant')
        self.engine.submit(action,principal='inventory')
        return action

    def test_independent_branch_continues_after_violation(self):
        self.queue_inventory()
        result=self.execute(self.action(resource_id='restricted'))
        self.assertEqual(result['status'],'denied')
        self.assertEqual(self.engine.reconcile('stock')['status'],'queued')
        self.assertTrue(self.engine.continuation('stock')['eligible'])
        self.assertEqual(self.engine.dispatch('stock',principal='inventory')['status'],'completed')
        self.assertTrue(any(e['kind']=='continuation_allowed' for e in self.engine.events()))
        self.assertEqual(self.engine.inspect()['receipt_count'],1)

    def test_consumed_output_propagates_containment(self):
        self.execute()
        self.engine.consume('inventory','req')
        self.queue_inventory()
        self.execute(self.action('bad',resource_id='restricted'))
        self.assertEqual(self.engine.reconcile('stock')['status'],'cancelled')
        self.assertFalse(self.engine.continuation('stock')['eligible'])
        self.assertTrue(all(c['quarantined'] for c in self.engine.graph()['contexts']))

    def test_shared_memory_causes_wider_pause(self):
        self.engine.grant('shared','shared-worker','review',ttl=100)
        self.engine.open_context('shared','shared','supplier-memory')
        self.execute(self.action(resource_id='restricted'))
        contexts={c['context_id']:c for c in self.engine.graph()['contexts']}
        self.assertEqual(contexts['shared']['quarantined'],1)
        self.assertEqual(contexts['inventory']['quarantined'],0)

    def test_quarantined_output_cannot_be_delivered(self):
        self.execute()
        self.engine.contain('supplier','Owner incident')
        result=self.engine.consume('inventory','req')
        self.assertNotIn('output',result)
        self.assertIn('inventory',result['contexts'])

    def test_missing_provenance_pauses_whole_task(self):
        self.queue_inventory()
        result=self.engine.consume('supplier','missing')
        self.assertEqual(result['contexts'],['inventory','supplier'])
        self.assertEqual(self.engine.reconcile('stock')['status'],'cancelled')

    def test_new_unregistered_grant_cannot_bypass_managed_task(self):
        self.engine.grant('new','worker','review',ttl=100)
        result=self.execute(self.action(grant_id='new'))
        self.assertEqual(result['reason'],'missing_context')
        self.assertEqual(self.engine.inspect()['receipt_count'],0)

    def test_late_enrollment_rejected(self):
        self.execute()
        with self.assertRaises(GuardError):self.engine.manage('review')

    def test_delegation_narrows_and_cascades(self):
        permissions=[{'operation':'read_file','resource_id':'input','resource_version':1}]
        self.engine.delegate('grant','child','child-worker',permissions,50)
        self.engine.open_context('child','child','child-memory')
        denied=self.action('child-write',grant_id='child',operation='write_note',content='Forbidden delegation')
        result=self.engine.submit(denied,principal='child-worker')
        self.assertEqual(result['reason'],'delegated_scope_violation')
        self.assertEqual(self.engine.inspect()['note_count'],0)
        # Upstream context remains clean; a child failure does not imply reverse consumption.
        self.assertEqual(next(c for c in self.engine.graph()['contexts'] if c['context_id']=='supplier')['quarantined'],0)

    def test_delegation_expiry_and_amplification_rejected(self):
        for permissions,ttl in [([{'operation':'read_file','resource_id':'restricted','resource_version':1}],50),
                                ([{'operation':'read_file','resource_id':'input','resource_version':1}],101)]:
            with self.assertRaises(GuardError):self.engine.delegate('grant','bad','child',permissions,ttl)

    def test_revocation_reaches_child_without_context(self):
        self.engine.delegate('grant','child','child-worker',[{'operation':'read_file','resource_id':'input','resource_version':1}],50)
        result=self.engine.revoke('grant')
        self.assertIn('child',result['revoked_grants'])
        with self.assertRaises(GuardError):self.engine.open_context('child','child','new-memory')

    def test_delegated_context_depends_on_parent(self):
        self.engine.delegate('grant','child','child-worker',[{'operation':'read_file','resource_id':'input','resource_version':1}],50)
        self.engine.open_context('child','child','child-memory')
        self.engine.contain('supplier','Parent compromised')
        self.assertEqual(next(c for c in self.engine.graph()['contexts'] if c['context_id']=='child')['quarantined'],1)

    def test_context_and_graph_survive_restart(self):
        self.execute()
        engine=Engine(self.db,clock=lambda:1000)
        self.assertEqual(engine.graph(),self.engine.graph())
        engine.consume('inventory','req')
        engine.contain('supplier','Incident')
        self.assertEqual(next(c for c in engine.graph()['contexts'] if c['context_id']=='inventory')['quarantined'],1)

    def test_historical_permit_not_reusable_after_input_change(self):
        self.execute()
        self.queue_inventory()
        self.assertTrue(self.engine.continuation('stock')['eligible'])
        self.engine.consume('inventory','req')
        self.engine.contain('supplier','New information')
        self.assertEqual(self.engine.dispatch('stock',principal='inventory')['status'],'cancelled')

    def test_forged_principal_cannot_quarantine_another_context(self):
        result=self.engine.submit(self.action(resource_id='restricted'),principal='attacker')
        self.assertEqual(result['reason'],'principal_mismatch')
        self.assertFalse(any(c['quarantined'] for c in self.engine.graph()['contexts']))

    def test_graph_and_effect_rollback_together(self):
        self.engine.submit(self.action(),principal='worker')
        before=self.engine.graph()
        with patch.object(self.engine,'_after_effect',side_effect=RuntimeError('crash')):
            with self.assertRaises(RuntimeError):self.engine.dispatch('req',principal='worker')
        self.assertEqual(before,self.engine.graph())
        self.assertEqual(self.engine.inspect()['receipt_count'],0)

    def test_consume_enforces_receiver_scope(self):
        self.execute()
        self.engine.approve(replace(self.scope,task_id='other',permissions=(Permission('read_file','restricted',1),)),reason='Restricted only')
        self.engine.manage('other');self.engine.grant('other','other','other',ttl=100)
        self.engine.open_context('other','other','other-memory')
        with self.assertRaises(GuardError):self.engine.consume('other','req')

    def test_consumption_counts_in_budget_and_behavior(self):
        self.execute()
        self.engine.consume('inventory','req')
        self.assertEqual(self.engine.inspect()['tasks'][0]['used_actions'],2)
        with self.engine.store.transaction() as db:
            self.assertEqual(len(self.engine._history(db,'review')),2)

    def test_unknown_lineage_expands_pause(self):
        self.assertEqual(self.engine.contain('supplier','Unobserved shared state',True)['contexts'],['inventory','supplier'])

    def test_quarantined_memory_cannot_be_reused(self):
        self.engine.contain('supplier','Incident')
        self.engine.grant('fresh','worker','review',ttl=100)
        with self.assertRaises(GuardError):self.engine.open_context('fresh','fresh','supplier-memory')

    def test_reserved_label_validation_regression(self):
        self.public.write_text('fresh');self.engine.import_file('input',self.public)
        with self.assertRaises(GuardError):self.engine.label('input',2,'unlabeled',2)

    def test_parallel_dispatch_and_containment_are_serialized(self):
        self.queue_inventory()
        def dispatch():return Engine(self.db,clock=lambda:1000).dispatch('stock',principal='inventory')
        def contain():return Engine(self.db,clock=lambda:1000).contain('inventory','Race test')
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(dispatch);b=pool.submit(contain);result=a.result();b.result()
        self.assertIn(result['status'],('completed','cancelled'))
        self.assertEqual(self.engine.inspect()['receipt_count'],int(result['status']=='completed'))

    def test_malformed_delegation_rejected_without_grant(self):
        for data in ([None],[{'operation':'read_file'}],[{'operation':'read_file','resource_id':'input','resource_version':1,'approved':True}]):
            with self.assertRaises(GuardError):self.engine.delegate('grant','bad','child',data,50)
        self.assertFalse(any(g['grant_id']=='bad' for g in self.engine.inspect()['grants']))

    def test_grandchild_revocation_and_shared_memory_cycles_terminate(self):
        permissions=[{'operation':'read_file','resource_id':'input','resource_version':1}]
        self.engine.delegate('grant','child','child',permissions,50)
        self.engine.open_context('child','child','supplier-memory')
        self.engine.delegate('child','grandchild','grandchild',permissions,25)
        self.engine.open_context('grandchild','grandchild','fresh')
        result=self.engine.contain('supplier','Incident')
        self.assertEqual(result['revoked_grants'],['child','grandchild','grant'])
