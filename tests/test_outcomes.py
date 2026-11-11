import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
spec = importlib.util.spec_from_file_location('stratagent_outcome_tests', SCRIPTS / 'compare_outcomes.py')
outcomes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(outcomes)


class OutcomeTests(unittest.TestCase):
    def test_separate_implementations_and_identical_task_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left, right = root / 'left', root / 'right'
            left.mkdir()
            right.mkdir()
            (left / 'README.md').write_text('Task A')
            (right / 'README.md').write_text('Task B')
            with self.assertRaises(ValueError):
                outcomes.compare(left, left, 'unused', 'host', 'model')
            with self.assertRaises(ValueError):
                outcomes.compare(left, right, 'unused', 'host', 'model')

    def test_failed_or_non_json_program_cannot_claim_task_acceptance(self):
        import sys
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'README.md').write_text('Original task')
            (root / 'inventory.py').write_text('print("not JSON")\n')
            report = outcomes.evaluate(root, sys.executable)
            self.assertEqual(report['passed'], 0)
            self.assertFalse(report['all_passed'])
            self.assertTrue(report['candidate_and_readme_preserved'])

    def test_saved_actual_implementations_retain_actual_platform_outcomes(self):
        import sys
        root = SCRIPTS.parent / 'examples/outcomes/inventory-cli'
        report = outcomes.compare(root / 'baseline', root / 'assisted', sys.executable, 'fixture', 'not launched')
        self.assertEqual(report['accepted_case_delta'], report['stratagent']['passed'] - report['baseline']['passed'])
        self.assertTrue(report['baseline']['all_passed'])
        self.assertEqual(report['baseline']['total'], 22)
        self.assertEqual(report['stratagent']['total'], 22)
        self.assertFalse(report['labels_attested'])

    def test_record_only_retains_failed_candidate_cases_without_claiming_a_pass(self):
        import json
        import subprocess
        import sys
        baseline = SCRIPTS.parent / 'examples/outcomes/inventory-cli/baseline'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'README.md').write_bytes((baseline / 'README.md').read_bytes())
            (root / 'inventory.py').write_text('print("not JSON")\n')
            report = root / 'result.json'
            process = subprocess.run([sys.executable, str(SCRIPTS / 'compare_outcomes.py'), '--baseline', str(baseline),
                                      '--assisted', str(root), '--host', 'fixture', '--model', 'not launched',
                                      '--output', str(report), '--record-only'], capture_output=True, timeout=30)
            self.assertEqual(process.returncode, 0, process.stderr)
            result = json.loads(report.read_text())
            self.assertEqual(result['outcome'], 'baseline-more-cases')
            self.assertEqual(result['stratagent']['passed'], 0)
            self.assertFalse(result['stratagent']['all_passed'])
            self.assertTrue(all(not row['passed'] for row in result['stratagent']['cases']))
