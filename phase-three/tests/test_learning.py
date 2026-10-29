from dataclasses import replace
import json
from unittest.mock import patch
from test_engine import Environment
from decisionguard.contracts import GuardError, Permission
from decisionguard.engine import Engine


class LearningTests(Environment):
    def train(self):
        ids=[]
        for i in range(8):
            task=f'train-{i}'
            self.engine.approve(replace(self.scope,task_id=task),reason='Training task')
            self.engine.grant(f'g-{i}','worker',task,ttl=100)
            action=self.action(f'r-{i}',task_id=task,grant_id=f'g-{i}')
            self.execute(action)
            self.engine.approve_trace(f'trace-{i}',task,'train','Reviewed benign')
            ids.append(f'trace-{i}')
        self.engine.train('review',ids)
        return ids

    def test_normal_action_matches_learned_profile(self):
        self.train()
        result=self.execute()
        self.assertEqual(result['behavior']['baseline_status'],'active')
        self.assertEqual(result['behavior']['signals'],[])
        self.assertEqual(result['behavior']['risk_priority'],0)

    def test_cold_start_is_explicit_and_not_an_attack(self):
        result=self.execute()
        self.assertEqual(result['behavior']['baseline_status'],'cold_start')
        self.assertEqual(result['status'],'completed')

    def test_unusual_write_held_before_effect_and_reviewed(self):
        self.train()
        action=self.action(operation='write_note',content='A novel but authorized note')
        result=self.execute(action)
        self.assertEqual(result['status'],'held')
        self.assertGreaterEqual(len(result['behavior']['signals']),2)
        self.assertEqual(result['behavior']['risk_priority'],20)
        self.assertIsNone(result['receipt'])
        self.assertEqual(self.engine.inspect()['note_count'],0)
        self.engine.review('req','Owner verified the new operation')
        result=self.engine.dispatch('req',principal='worker')
        self.assertEqual(result['status'],'completed')
        self.assertEqual(self.engine.inspect()['note_count'],1)

    def test_profile_and_held_state_survive_restart(self):
        self.train()
        self.execute(self.action(operation='write_note',content='Review me'))
        engine=Engine(self.db,clock=lambda:1000)
        self.assertEqual(engine.reconcile('req')['status'],'held')
        engine.review('req','Checked after restart')
        self.assertEqual(engine.dispatch('req',principal='worker')['status'],'completed')

    def test_review_cannot_bypass_revocation(self):
        self.train()
        self.execute(self.action(operation='write_note',content='Review me'))
        self.engine.review('req','Allowed novelty')
        self.engine.revoke('grant')
        self.assertEqual(self.engine.dispatch('req',principal='worker')['status'],'cancelled')
        self.assertEqual(self.engine.inspect()['note_count'],0)

    def test_new_profile_invalidates_previous_release(self):
        ids=self.train()
        self.execute(self.action(operation='write_note',content='Review me'))
        self.engine.review('req','Allowed novelty')
        self.engine.train('review',ids)
        self.assertEqual(self.engine.dispatch('req',principal='worker')['status'],'held')

    def test_scope_change_keeps_hard_denial_authoritative(self):
        self.train()
        self.engine.approve(self.scope,reason='New scope')
        result=self.execute()
        self.assertEqual(result['reason'],'stale_scope')
        self.assertEqual(result['behavior']['evidence_severity'],3)
        self.engine.grant('new','worker','review',ttl=100)
        result=self.execute(self.action('new-action',grant_id='new',operation='write_note',content='hello'))
        self.assertEqual(result['behavior']['baseline_status'],'stale_profile')
        self.assertEqual(result['status'],'held')

    def test_unlabeled_write_is_held_without_invented_risk(self):
        self.public.write_text('New resource')
        self.engine.import_file('input',self.public)
        self.engine.approve(replace(self.scope,permissions=(Permission('write_note','input',2),)),reason='New input')
        self.engine.grant('new','worker','review',ttl=100)
        result=self.execute(self.action(resource_version=2,grant_id='new',operation='write_note',content='note'))
        self.assertEqual(result['status'],'held')
        self.assertIsNone(result['behavior']['risk_priority'])

    def test_single_novelty_does_not_hold_read(self):
        self.train()
        self.execute()
        result=self.execute(self.action('second'))
        self.assertEqual(result['status'],'completed')
        self.assertTrue(result['behavior']['signals'])

    def test_live_activity_never_updates_baseline(self):
        self.train()
        before=self.sql('SELECT body,digest FROM profiles')
        self.execute()
        self.execute(self.action('second'))
        self.assertEqual(before,self.sql('SELECT body,digest FROM profiles'))

    def test_training_partitions_and_source_task_disjointness(self):
        ids=self.train()
        self.execute()
        self.engine.approve_trace('held-out','review','test','Benign held-out run')
        with self.assertRaises(GuardError):
            self.engine.train('review',ids+['held-out'])
        with self.assertRaises(GuardError):
            self.engine.approve_trace('duplicate','review','train','Try to relabel')
        with self.assertRaises(GuardError):
            self.engine.evaluate_profile('review',ids)
        report=self.engine.evaluate_profile('review',['held-out'])
        self.assertEqual(report['traces'][0]['flagged_actions'],0)
        self.assertEqual(report['traces'][0]['hypothetical_holds'],0)
        self.assertEqual(report['traces'][0]['actions'],1)

    def test_trace_and_profile_tampering_fails_closed(self):
        ids=self.train()
        self.sql("UPDATE traces SET digest='bad' WHERE trace_id=?",(ids[0],))
        with self.assertRaises(GuardError):
            self.engine.train('review',ids)
        self.sql("UPDATE profiles SET digest='bad'")
        with self.assertRaises(GuardError):
            self.execute()
        self.assertEqual(self.engine.reconcile('req')['status'],'not_found')

    def test_labels_cannot_be_silently_changed(self):
        with self.assertRaises(GuardError):
            self.engine.label('input',1,'different',5)

    def test_fewer_than_three_traces_rejected(self):
        with self.assertRaises(GuardError):
            self.engine.train('review',[])

    def test_hard_denial_cannot_be_reviewed(self):
        self.train()
        result=self.execute(self.action(resource_id='restricted'))
        self.assertEqual(result['status'],'denied')
        self.assertEqual(result['behavior']['risk_priority'],60)
        with self.assertRaises(GuardError):
            self.engine.review('req','Cannot override scope')
