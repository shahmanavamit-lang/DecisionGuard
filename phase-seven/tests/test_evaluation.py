import importlib.util
import json
from pathlib import Path
from test_engine import Environment, ROOT

spec=importlib.util.spec_from_file_location('evaluation',ROOT/'evals/run.py')
evaluation=importlib.util.module_from_spec(spec);spec.loader.exec_module(evaluation)


class EvaluationTests(Environment):
    def test_all_modes_and_frozen_gates(self):
        report=evaluation.evaluate(self.root/'evaluation',variants=1)
        self.assertEqual(len(report['runs']),32)
        self.assertTrue(report['passed'],report['gates'])
        by={(r['mode'],r['case']):r for r in report['runs']}
        self.assertEqual(by['selective','outside_independent']['harmful_effects'],0)
        self.assertTrue(by['selective','outside_independent']['inventory_completed'])
        self.assertFalse(by['whole_pause','outside_independent']['inventory_completed'])
        self.assertEqual(by['credentials_model','outside_independent']['harmful_effects'],1)
        self.assertEqual(by['selective','overbroad_scope']['harmful_effects'],1)
        self.assertGreater(by['selective','benign_novelty']['benign_interventions'],0)
        self.assertEqual(report['summary']['selective']['preserved_independent_steps']['denominator'],2)
        self.assertTrue(report['source_sha256'])
        with self.assertRaises(FileExistsError):evaluation.evaluate(self.root/'evaluation',1)

    def test_reproducible_outcomes_for_fixed_seed(self):
        a=evaluation.case_run(self.root/'a','outside_independent','selective',123)
        b=evaluation.case_run(self.root/'b','outside_independent','selective',123)
        for key in ('receipts','decisions','harmful_effects','complete_task','inventory_completed'):
            self.assertEqual(a[key],b[key],key)

    def prepare_delivery(self):
        self.engine.manage('review');self.engine.open_context('source','grant','source-memory')
        self.execute()
        self.engine.grant('receiver','receiver','review',ttl=100)
        self.engine.open_context('receiver','receiver','receiver-memory')

    def test_corrupted_output_is_not_delivered_or_charged(self):
        self.prepare_delivery()
        self.sql("UPDATE output_data SET body=? WHERE node_id='o:req'",(json.dumps({'content':'CORRUPTED','resource_version':1}),))
        before=self.engine.inspect()['tasks'][0]['used_actions']
        result=self.engine.consume('receiver','req')
        self.assertNotIn('output',result)
        self.assertEqual(result['reason'],'output_integrity_failure')
        self.assertEqual(self.engine.inspect()['tasks'][0]['used_actions'],before)
        self.assertEqual(self.engine.inspect()['receipt_count'],1)
        self.assertTrue(all(c['quarantined'] for c in self.engine.graph()['contexts']))

    def test_missing_output_data_conservatively_contains(self):
        self.prepare_delivery();self.sql("DELETE FROM output_data WHERE node_id='o:req'")
        self.assertEqual(self.engine.consume('receiver','req')['reason'],'incomplete_output_provenance')

    def test_malformed_output_data_conservatively_contains(self):
        self.prepare_delivery();self.sql("UPDATE output_data SET body='{' WHERE node_id='o:req'")
        self.assertEqual(self.engine.consume('receiver','req')['reason'],'output_integrity_failure')

    def test_output_version_and_receipt_mismatch_fail_closed(self):
        self.prepare_delivery();self.sql("UPDATE receipts SET resource_version=99 WHERE request_id='req'")
        self.assertEqual(self.engine.consume('receiver','req')['reason'],'output_integrity_failure')
