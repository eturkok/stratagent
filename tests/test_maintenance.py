import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from stratagent.cli import main
from stratagent.common import StratagentError
from stratagent.context import configure
from stratagent.maintenance import BASELINE, handoff, maintain, render
from stratagent.service import Stratagent
from test_stratagent import file_state


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.service = Stratagent(self.root)
        self.service.init('Build a Python API with tests. No payments.', ['codex'])

    def record(self):
        report = maintain(self.service)
        return maintain(self.service, report['approval'], True)

    def install(self):
        stage = self.service.stage('blueprint')
        self.service.apply_stage(stage['stage_id'], stage['plan']['approval'])

    def test_readonly_checkpoint_and_idempotent_record_do_not_change_project(self):
        (self.root / 'original.txt').write_text('preserve me')
        before = file_state(self.root)
        with patch('urllib.request.urlopen', side_effect=AssertionError('network')):
            report = maintain(self.service)
            self.assertEqual(report['status'], 'no-checkpoint')
            self.assertEqual(before, file_state(self.root))
            saved = self.record()
            self.assertTrue(saved['checkpoint_recorded'])
            self.assertEqual(maintain(self.service)['status'], 'unchanged')
            stable = file_state(self.root)
            self.record()
            self.assertEqual(stable, file_state(self.root))
        self.assertEqual((self.root / 'original.txt').read_text(), 'preserve me')

    def test_dependencies_definitions_documents_and_removals_appear_in_one_report(self):
        (self.root / 'README.md').write_text('Python API architecture')
        preview = configure(self.service.ws, ['README.md'])
        configure(self.service.ws, ['README.md'], preview['approval'], True)
        self.record()
        (self.root / 'README.md').write_text('Python API with Redis caching')
        (self.root / 'pyproject.toml').write_text('[project]\ndependencies=["fastapi", "pytest"]\n')
        (self.root / 'AGENTS.md').write_text('Existing user guidance')
        report = maintain(self.service)
        self.assertEqual(report['status'], 'review')
        self.assertEqual({row['path'] for row in report['changes'] if 'path' in row},
                         {'document:README.md', 'manifest:pyproject.toml', 'definition:AGENTS.md'})
        self.record()
        (self.root / 'AGENTS.md').unlink()
        self.assertIn({'area': 'observations', 'path': 'definition:AGENTS.md', 'action': 'removed'}, maintain(self.service)['changes'])

    def test_changed_request_and_policy_are_visible_but_checkpoint_grants_no_plan_authority(self):
        self.record()
        manifest = self.service.manifest()
        manifest['analysis']['prompt'] = 'Build a Python API with tests and privacy. No payments.'
        self.service.ws.write('.stratagent/manifest.json', manifest)
        self.service.allow('example/skills')
        areas = {row['area'] for row in maintain(self.service)['changes']}
        self.assertTrue({'request', 'policy'} <= areas)
        self.assertFalse(self.service.lock()['installations'])

    def test_stale_approval_and_approval_without_record_are_refused(self):
        report = maintain(self.service)
        (self.root / 'AGENTS.md').write_text('New guidance')
        with self.assertRaises(StratagentError):
            maintain(self.service, report['approval'], True)
        with self.assertRaises(StratagentError):
            maintain(self.service, report['approval'])
        self.assertFalse((self.root / BASELINE).exists())

    def test_pending_recovery_prevents_recording_and_handoff_claims_attention(self):
        with patch('stratagent.maintenance.Transactions.pending', return_value={'id': 'interrupted'}):
            report = maintain(self.service)
            self.assertEqual(report['status'], 'attention')
            with self.assertRaises(StratagentError):
                maintain(self.service, report['approval'], True)
            self.assertEqual(handoff(self.service, 'claude')['status'], 'attention')

    def test_revoked_installed_source_is_not_hidden_by_matching_file_hashes(self):
        self.install()
        lock = self.service.lock()
        lock['installations']['workspace-blueprint']['source']['reviewed_sources'] = [
            {'kind': 'skill', 'review': {'repo': 'example/skills', 'review_digest': 'a' * 64}}]
        self.service.ws.write('.stratagent/lock.json', lock)
        policy = self.service.policy()
        policy['revocations'] = [{'subject': 'repo:example/skills', 'reason': 'Withdrawn resource'}]
        self.service.ws.write('.stratagent/policy.json', policy)
        self.assertEqual(maintain(self.service)['status'], 'attention')

    def test_drift_and_missing_managed_file_cannot_be_accepted_as_a_clean_checkpoint(self):
        self.install()
        self.record()
        output = self.service.lock()['installations']['workspace-blueprint']['outputs'][0]['path']
        (self.root / output).write_text('User changes are preserved')
        report = maintain(self.service)
        self.assertEqual(report['status'], 'attention')
        with self.assertRaises(StratagentError):
            maintain(self.service, report['approval'], True)
        (self.root / output).unlink()
        self.assertIn({'path': output, 'reason': 'missing'}, maintain(self.service)['blockers'])

    def test_scan_opt_out_does_not_read_project_definitions_or_selected_files(self):
        manifest = self.service.manifest()
        manifest['analysis']['project'] = None
        self.service.ws.write('.stratagent/manifest.json', manifest)
        (self.root / 'AGENTS.md').write_bytes(b'x' * 300000)
        report = maintain(self.service)
        self.assertFalse(report['snapshot']['project_scan'])
        self.assertEqual(report['snapshot']['observations'], {})
        self.assertFalse(report['blockers'])

    def test_invalid_checkpoint_is_preserved_and_refused(self):
        (self.root / BASELINE).write_text('{"schema_version":99}')
        with self.assertRaises(StratagentError):
            maintain(self.service)
        self.assertEqual((self.root / BASELINE).read_text(), '{"schema_version":99}')

    @unittest.skipIf(os.name == 'nt', 'POSIX FIFO')
    def test_metadata_fifo_and_redirect_are_refused_without_blocking(self):
        manifest = self.root / '.stratagent/manifest.json'
        data = manifest.read_bytes()
        manifest.unlink()
        os.mkfifo(manifest)
        with self.assertRaises(StratagentError):
            maintain(self.service)
        manifest.unlink()
        other = self.root / 'external.json'
        other.write_bytes(data)
        manifest.symlink_to(other)
        with self.assertRaises(StratagentError):
            handoff(self.service, 'claude')

    def test_handoff_is_inert_and_omits_document_bodies_approvals_and_local_paths(self):
        (self.root / 'README.md').write_text('private-document-marker')
        selection = configure(self.service.ws, ['README.md'])
        configure(self.service.ws, ['README.md'], selection['approval'], True)
        self.install()
        before = file_state(self.root)
        with patch('urllib.request.urlopen', side_effect=AssertionError('network')):
            report = handoff(self.service, 'claude')
        self.assertEqual(before, file_state(self.root))
        self.assertEqual(report['project']['request'], self.service.manifest()['analysis']['prompt'])
        self.assertEqual(report['target_host'], 'claude')
        self.assertTrue(report['roles'])
        self.assertTrue(report['installed_context_current'])
        text = json.dumps(report)
        for private in ('private-document-marker', selection['approval'], str(self.root)):
            self.assertNotIn(private, text)
        self.assertFalse(report['files_changed'])
        self.assertIn('No search', render(report))
        (self.root / 'README.md').write_text('Changed selected architecture')
        self.assertFalse(handoff(self.service, 'claude')['installed_context_current'])

    def test_handoff_never_invents_an_installed_decision_or_exports_credential_text(self):
        report = handoff(self.service, 'generic')
        self.assertEqual(report['roles'], [])
        self.assertIsNone(report['installed_context_current'])
        manifest = self.service.manifest()
        manifest['analysis']['prompt'] += ' secret=abcdefghijklmnopqrstuv'
        self.service.ws.write('.stratagent/manifest.json', manifest)
        with self.assertRaisesRegex(StratagentError, 'credential'):
            handoff(self.service, 'claude')

    def test_cli_human_and_json_views_work_without_automatic_writes(self):
        before = file_state(self.root)
        for command in (['maintain'], ['maintain', '--json'], ['handoff', '--host', 'claude', '--json']):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main([*command, '--workspace', str(self.root)]), 0)
            self.assertIn('StratAgent' if '--json' not in command else 'schema_version', output.getvalue())
        self.assertEqual(before, file_state(self.root))
