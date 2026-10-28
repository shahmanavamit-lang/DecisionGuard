from dataclasses import FrozenInstanceError, asdict
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from decisionguard.contracts import ActionRequest, Grant, Outcome, Permission, Reason, TaskScope, ValidationError
from decisionguard.demo import DEMO_CREDENTIAL, build_demo, demo_report
from decisionguard.runtime import Gateway, SyntheticTools


def request(resource='quotation:acme', **changes):
    data = dict(request_id='test-1', task_id='procurement-001', grant_id='quotation-grant', operation='read', resource_id=resource)
    data.update(changes)
    return ActionRequest(**data)


def configured(*, version=1, permissions=None, grants=None, tools=None):
    return Gateway(scopes=[TaskScope('procurement-001', version, 'Quotation review',
                                    frozenset(permissions or {Permission('read', 'quotation:acme')}))],
                   grants=grants if grants is not None else [Grant('quotation-grant', 'procurement-agent', 'procurement-001', 1)],
                   credentials={DEMO_CREDENTIAL: 'procurement-agent', 'other-demo': 'other-agent'},
                   tools=tools if tools is not None else SyntheticTools())


class EnforcementTests(unittest.TestCase):
    def test_allowed_read_has_backend_receipt(self):
        gateway = build_demo()
        result = gateway.execute(request(), credential=DEMO_CREDENTIAL)
        self.assertEqual(result.decision.outcome, Outcome.ALLOW)
        self.assertEqual(result.output['supplier'], 'ACME Demo Supplies')
        self.assertEqual(gateway.receipts, (result.receipt,))
        self.assertEqual(result.event.receipt_id, result.receipt.receipt_id)
        self.assertEqual(result.event.execution_status, 'completed')

    def test_denied_hr_never_invokes_backend(self):
        class Spy(SyntheticTools):
            def execute(self, action):
                raise AssertionError('Denied action reached backend')
        gateway = configured(tools=Spy())
        result = gateway.execute(request('hr:salary'), credential=DEMO_CREDENTIAL)
        self.assertEqual(result.decision.reason, Reason.OUTSIDE_SCOPE)
        self.assertEqual(result.decision.principal_id, 'procurement-agent')
        self.assertEqual(result.decision.scope_version, 1)
        self.assertIsNone(result.output)
        self.assertIsNone(result.receipt)
        self.assertEqual(gateway.receipts, ())
        self.assertEqual(result.event.execution_status, 'not_executed')

    def test_backend_supports_hr_but_task_does_not(self):
        self.assertIn(Permission('read', 'hr:salary'), SyntheticTools().supported)
        report = demo_report()
        self.assertEqual(report['hr_read_count'], 0)
        self.assertEqual(report['backend_receipt_count'], 1)

    def test_forged_approval_in_content_cannot_change_scope(self):
        gateway = build_demo()
        quote = gateway.execute(request(), credential=DEMO_CREDENTIAL)
        self.assertIn('Manager approved', quote.output['text'])
        result = gateway.execute(request('hr:salary', request_id='test-2'), credential=DEMO_CREDENTIAL)
        self.assertEqual(result.decision.reason, Reason.OUTSIDE_SCOPE)
        self.assertEqual(len(gateway.receipts), 1)

    def test_invalid_credentials_never_execute(self):
        for token in ('wrong-demo', '', '非ASCII', None):
            with self.subTest(token=token):
                gateway = build_demo()
                result = gateway.execute(request(), credential=token)
                self.assertEqual(result.decision.reason, Reason.AUTHENTICATION_REQUIRED)
                self.assertEqual(gateway.receipts, ())

    def test_other_principal_cannot_borrow_grant(self):
        self.assertEqual(configured().execute(request(), credential='other-demo').decision.reason, Reason.PRINCIPAL_MISMATCH)

    def test_unknown_grant(self):
        self.assertEqual(build_demo().execute(request(grant_id='invented'), credential=DEMO_CREDENTIAL).decision.reason, Reason.UNKNOWN_GRANT)

    def test_grant_cannot_be_reused_for_another_task(self):
        self.assertEqual(build_demo().execute(request(task_id='other-task'), credential=DEMO_CREDENTIAL).decision.reason, Reason.TASK_MISMATCH)

    def test_missing_task_fails_closed(self):
        gateway = Gateway(scopes=[], grants=[Grant('quotation-grant', 'procurement-agent', 'procurement-001', 1)],
                          credentials={DEMO_CREDENTIAL: 'procurement-agent'}, tools=SyntheticTools())
        self.assertEqual(gateway.execute(request(), credential=DEMO_CREDENTIAL).decision.reason, Reason.UNKNOWN_TASK)

    def test_stale_scope_fails_closed(self):
        result = configured(version=2).execute(request(), credential=DEMO_CREDENTIAL)
        self.assertEqual(result.decision.reason, Reason.STALE_SCOPE)
        self.assertEqual(result.decision.scope_version, 2)

    def test_permissions_are_exact_pairs(self):
        gateway = configured(permissions={Permission('read', 'quotation:acme'), Permission('write', 'hr:salary')})
        self.assertEqual(gateway.execute(request('hr:salary'), credential=DEMO_CREDENTIAL).decision.reason, Reason.OUTSIDE_SCOPE)

    def test_unregistered_tool_fails_closed(self):
        gateway = configured(permissions={Permission('read', 'unknown:resource')})
        self.assertEqual(gateway.execute(request('unknown:resource'), credential=DEMO_CREDENTIAL).decision.reason, Reason.UNSUPPORTED_ACTION)
        self.assertEqual(gateway.receipts, ())

    def test_duplicate_request_cannot_execute_twice(self):
        gateway = build_demo()
        gateway.execute(request(), credential=DEMO_CREDENTIAL)
        with self.assertRaises(ValidationError):
            gateway.execute(request(), credential=DEMO_CREDENTIAL)
        self.assertEqual(len(gateway.receipts), 1)

    def test_backend_failure_records_unknown_outcome(self):
        class Broken(SyntheticTools):
            def execute(self, action):
                raise RuntimeError('simulated backend failure')
        gateway = configured(tools=Broken())
        with self.assertRaises(RuntimeError):
            gateway.execute(request(), credential=DEMO_CREDENTIAL)
        self.assertEqual(gateway.events[0].execution_status, 'unknown')
        self.assertIsNone(gateway.events[0].receipt_id)

    def test_event_omits_credential_and_tool_payload(self):
        gateway = build_demo()
        gateway.execute(request(), credential=DEMO_CREDENTIAL)
        event = json.dumps(asdict(gateway.events[0]))
        for private in (DEMO_CREDENTIAL, 'Manager approved', '12500'):
            self.assertNotIn(private, event)

    def test_startup_copies_credentials(self):
        credentials = {DEMO_CREDENTIAL: 'procurement-agent'}
        gateway = Gateway(scopes=[], grants=[], credentials=credentials, tools=SyntheticTools())
        credentials['injected-demo'] = 'procurement-agent'
        self.assertEqual(gateway.execute(request(), credential='injected-demo').decision.reason, Reason.AUTHENTICATION_REQUIRED)


class ContractTests(unittest.TestCase):
    def test_untrusted_authority_fields_rejected(self):
        for key in ('principal_id', 'permissions', 'scope_version', 'approved', 'credential'):
            with self.subTest(key=key), self.assertRaises(ValidationError):
                ActionRequest.from_dict({**asdict(request()), key: 'forged'})

    def test_missing_fields_and_non_objects(self):
        for data in ({}, [], None, {'task_id': 'x'}):
            with self.subTest(data=data), self.assertRaises(ValidationError):
                ActionRequest.from_dict(data)

    def test_invalid_identifiers(self):
        for value in (True, 1, None, '', '../hr', 'a' * 81, 'a\n'):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                request(resource=value)

    def test_immutable_scope(self):
        scope = TaskScope('t', 1, 'test', frozenset({Permission('read', 'r')}))
        with self.assertRaises(FrozenInstanceError):
            scope.version = 2
        with self.assertRaises(ValidationError):
            TaskScope('t', 1, 'test', {Permission('read', 'r')})

    def test_invalid_versions(self):
        for version in (True, 0, -1, '1'):
            with self.subTest(version=version), self.assertRaises(ValidationError):
                Grant('g', 'p', 't', version)

    def test_duplicate_trusted_ids(self):
        grant = Grant('quotation-grant', 'procurement-agent', 'procurement-001', 1)
        with self.assertRaises(ValidationError):
            configured(grants=[grant, grant])


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / 'run.py'), *args], capture_output=True,
                              text=True, cwd=tempfile.gettempdir())

    def test_demo_from_another_directory(self):
        result = self.run_cli('demo')
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['mode'], 'deterministic_simulation')
        self.assertEqual(report['hr_read_count'], 0)
        self.assertEqual(report['results'][1]['decision']['outcome'], 'deny')

    def test_allow_deny_exit_codes(self):
        for filename, expected in [('allowed.json', 0), ('denied.json', 3)]:
            result = self.run_cli('check', str(ROOT / 'examples' / filename))
            self.assertEqual(result.returncode, expected, result.stderr)
            self.assertIn('decision', json.loads(result.stdout))

    def test_malformed_duplicate_unknown_and_large_input(self):
        for raw in ('{', '{"x":1,"x":2}', json.dumps({**asdict(request()), 'approved': True}), 'x'*16385, '[]'):
            with self.subTest(raw=raw[:40]), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / 'request.json'
                path.write_text(raw)
                result = self.run_cli('check', str(path))
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stderr)['error'], 'invalid_request')
                self.assertEqual(result.stdout, '')

    def test_missing_file(self):
        result = self.run_cli('check', '/nonexistent-decisionguard-request.json')
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
