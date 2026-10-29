"""Subprocess walkthroughs use caller-provided temporary files, not application fixtures."""
import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / 'state.sqlite3'
        self.public = self.root / 'input.txt'
        self.content = uuid4().hex
        self.public.write_text(self.content)
        self.invoke('init')
        self.invoke('import-file', 'input', str(self.public))
        self.invoke('label','input','--version','1','--class','document','--impact','2')
        self.scope = self.root/'scope.json'
        self.scope.write_text(json.dumps({'task_id':'review','description':'User-file review',
            'permissions':[{'operation':'read_file','resource_id':'input','resource_version':1},
                           {'operation':'write_note','resource_id':'input','resource_version':1}],
            'max_actions':10,'max_bytes':10000}))
        self.invoke('approve', str(self.scope), '--reason', 'Local owner approval')
        self.invoke('grant', 'g', '--principal', 'worker', '--task', 'review', '--ttl', '3600')

    def command(self, *args):
        return [sys.executable, '-W', 'error::ResourceWarning', str(ROOT/'run.py'), '--db', str(self.db), *args]

    def invoke(self, *args, expected=0):
        result = subprocess.run(self.command(*args), cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        return json.loads(result.stdout if expected in (0,3) else result.stderr)

    def action(self, **changes):
        data={'request_id':'r','task_id':'review','grant_id':'g','operation':'read_file',
              'resource_id':'input','resource_version':1}
        data.update(changes)
        path=self.root/'action.json'
        path.write_text(json.dumps(data))
        return str(path)

    def test_persistent_walkthrough_across_processes(self):
        path=self.action()
        self.assertEqual(self.invoke('submit',path,'--principal','worker')['status'],'queued')
        completed=self.invoke('dispatch','r','--principal','worker')
        self.assertEqual(completed['output']['content'],self.content)
        self.assertEqual(self.invoke('reconcile','r'),completed)
        self.assertEqual(self.invoke('inspect')['receipt_count'],1)
        self.assertTrue(self.invoke('events'))

    def test_denied_and_invalid_inputs_have_documented_exit_codes(self):
        self.assertEqual(self.invoke('submit',self.action(resource_id='other'),'--principal','worker',expected=3)['reason'],'outside_scope')
        invalid=self.action(approved=True)
        self.assertEqual(self.invoke('submit',invalid,'--principal','worker',expected=2)['error'],'invalid_input')

    def test_revoke_then_dispatch_does_not_execute(self):
        self.invoke('submit',self.action(),'--principal','worker')
        self.invoke('revoke','g')
        self.assertEqual(self.invoke('dispatch','r','--principal','worker',expected=3)['status'],'cancelled')
        self.assertEqual(self.invoke('inspect')['receipt_count'],0)

    def test_concurrent_processes_do_not_duplicate_effect(self):
        self.invoke('submit',self.action(operation='write_note',content=uuid4().hex),'--principal','worker')
        processes=[subprocess.Popen(self.command('dispatch','r','--principal','worker'),stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,text=True) for _ in range(4)]
        results=[]
        for proc in processes:
            out,err=proc.communicate(timeout=10)
            self.assertEqual(proc.returncode,0,err)
            results.append(json.loads(out))
        self.assertTrue(all(r==results[0] for r in results))
        self.assertEqual(self.invoke('inspect')['note_count'],1)

    def test_missing_file_and_existing_database_fail_cleanly(self):
        self.invoke('init',expected=2)
        self.invoke('import-file','bad',str(self.root/'missing.txt'),expected=2)

    def test_user_file_walkthrough(self):
        restricted=self.root/'restricted.txt'
        restricted.write_text(uuid4().hex)
        note=self.root/'note.txt'
        note.write_text(uuid4().hex)
        result=subprocess.run([sys.executable,str(ROOT/'scripts'/'walkthrough.py'),
            '--input',str(self.public),'--restricted',str(restricted),'--note',str(note),
            '--workspace',str(self.root/'walkthrough')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual([r['status'] for r in report['actions']],
                         ['completed','denied','completed','completed','cancelled'])
        self.assertEqual(report['receipt_count'],3)
        self.assertEqual(report['note_count'],1)
        self.assertTrue(report['retry_returned_original_result'])

    def test_local_learning_walkthrough(self):
        note=self.root/'note.txt';note.write_text(uuid4().hex)
        result=subprocess.run([sys.executable,str(ROOT/'scripts'/'learning_walkthrough.py'),
            '--input',str(self.public),'--note',str(note),'--workspace',str(self.root/'learn')],
            capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual(report['held_action']['status'],'held')
        self.assertEqual(report['reviewed_action']['status'],'completed')
        self.assertEqual(report['held_out_evaluation']['traces'][0]['hypothetical_holds'],0)

    def test_managed_containment_walkthrough(self):
        result=subprocess.run([sys.executable,str(ROOT/'scripts/containment_walkthrough.py'),
            '--input',str(self.public),'--workspace',str(self.root/'containment')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual(report['independent']['inventory_status'],'completed')
        self.assertEqual(report['dependent']['inventory_status'],'cancelled')
        self.assertEqual(report['independent']['receipt_count'],2)
        self.assertEqual(report['dependent']['receipt_count'],1)

    def test_application_has_no_network_or_model_client_imports(self):
        forbidden={'socket','urllib','http','requests','httpx','openai','anthropic','subprocess'}
        for path in (ROOT/'src').rglob('*.py'):
            tree=ast.parse(path.read_text())
            imports=set()
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):
                    imports.update(alias.name.split('.')[0] for alias in node.names)
                elif isinstance(node,ast.ImportFrom) and node.module:
                    imports.add(node.module.split('.')[0])
            self.assertFalse(imports & forbidden, str(path))


if __name__=='__main__':
    unittest.main()
