import io
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from stratagent.cli import main
from stratagent.experience import setup
from stratagent.service import Stratagent
from test_stratagent import file_state


class SetupTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.service = Stratagent(self.root)

    def test_readonly_preview_and_exact_connection_reuse_bound_runtime_without_path(self):
        before = file_state(self.root)
        card = setup(self.service, ['codex'])
        self.assertEqual(file_state(self.root), before)
        self.assertEqual(card['setup']['host_loading'], 'not-observed')
        self.assertEqual(card['connection']['launcher'][0], sys.executable)
        self.assertEqual(card['connection']['launcher'][-2:], ['-m', 'stratagent'])
        text = next(iter(card['connection']['file_contents'].values()))
        self.assertIn(json.dumps(card['connection']['launcher']), text)
        result = subprocess.run(card['next_action']['argv'], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['setup']['instructions'], 'present')
        before = file_state(self.root)
        again = setup(self.service, ['codex'])
        self.assertTrue(again['connection']['already_connected'])
        self.assertEqual(file_state(self.root), before)
        self.assertFalse(self.service.ws.path('.stratagent/manifest.json').exists())

    def test_setup_host_alias_and_conflicting_user_skill_are_actionable_and_preserved(self):
        path = self.root / '.agents/skills/stratagent/SKILL.md'
        path.parent.mkdir(parents=True)
        path.write_text('User owned instructions')
        before = file_state(self.root)
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(['setup', '--host', 'codex', '--workspace', str(self.root), '--json']), 2)
        result = json.loads(out.getvalue())
        self.assertEqual(result['setup']['instructions'], 'conflict')
        self.assertEqual(file_state(self.root), before)

    def test_setup_without_host_asks_for_a_target_instead_of_adding_all_integrations(self):
        card = setup(self.service)
        self.assertEqual(card['phase'], 'choose-host')
        self.assertFalse(any(self.root.iterdir()))

    def test_failed_health_does_not_create_project_connection(self):
        with patch('stratagent.diagnostics.diagnose', return_value={'ok': False, 'checks': [{'id': 'runtime', 'status': 'fail'}]}):
            card = setup(self.service, ['codex'])
        self.assertEqual(card['phase'], 'setup-attention')
        self.assertFalse(any(self.root.iterdir()))

    def test_missing_dependency_is_explained_before_runtime_import_or_connection(self):
        with patch('stratagent.diagnostics._dependency_ready', return_value=False), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(['setup','--host','codex','--workspace',str(self.root),'--json']),2)
        result=json.loads(out.getvalue())
        self.assertEqual(result['phase'],'setup-attention')
        self.assertTrue(any(check['id']=='pyyaml-runtime' and check['status']=='fail' for check in result['health']['checks']))
        self.assertFalse(any(self.root.iterdir()))

    def test_launcher_change_invalidates_old_connection_approval(self):
        first = setup(self.service, ['codex'])
        with patch('stratagent.experience.sys.executable', '/a/different/python'):
            other = setup(self.service, ['codex'])
        self.assertNotEqual(first['connection']['approval'], other['connection']['approval'])
        self.assertFalse(any(self.root.iterdir()))


class InstallerPreservationTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('stratagent_installer', Path(__file__).resolve().parents[1] / 'scripts/install.py')
        self.installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.installer)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

    def test_older_python_is_actionable_without_creating_a_runtime(self):
        with patch.object(self.installer.sys, 'version_info', (3,10,0)):
            with self.assertRaisesRegex(ValueError, 'Python 3.11 or newer'):
                self.installer.install(self.root/'runtime')
        self.assertFalse((self.root/'runtime').exists())

    def test_unmarked_environment_is_never_adopted_even_with_upgrade(self):
        (self.root / 'user.txt').write_text('preserve me')
        for upgrade in (False, True):
            with self.assertRaisesRegex(ValueError, 'preserved'):
                self.installer.install(self.root, upgrade=upgrade)
        self.assertEqual((self.root / 'user.txt').read_text(), 'preserve me')
        self.assertEqual(len(list(self.root.iterdir())), 1)

    def test_offline_missing_wheel_is_rejected_before_creating_runtime(self):
        with self.assertRaisesRegex(ValueError, 'Offline wheelhouse'):
            self.installer.install(self.root / 'new', self.root)
        self.assertFalse((self.root / 'new').exists())

    def test_same_version_but_different_offline_source_is_rejected_before_installing(self):
        from zipfile import ZipFile
        from stratagent import __version__
        wheel = self.root / ('stratagent_cli-' + __version__ + '-py3-none-any.whl')
        with ZipFile(wheel, 'w') as archive:
            archive.writestr('stratagent/__init__.py', 'different code')
        with self.assertRaisesRegex(ValueError, 'differs from this reviewed checkout'):
            self.installer.install(self.root / 'runtime', self.root)
        self.assertFalse((self.root / 'runtime').exists())

    def test_invalid_or_redirected_receipt_does_not_launch_existing_runtime(self):
        (self.root / self.installer.MARKER).write_text('[]')
        with patch('subprocess.run', side_effect=AssertionError('must not execute')):
            with self.assertRaisesRegex(ValueError, 'receipt'):
                self.installer.install(self.root)
