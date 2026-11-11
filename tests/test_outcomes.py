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

    def test_saved_actual_implementations_reproduce_equal_acceptance(self):
        import sys
        root = SCRIPTS.parent / 'examples/outcomes/inventory-cli'
        report = outcomes.compare(root / 'baseline', root / 'assisted', sys.executable, 'fixture', 'not launched')
        self.assertEqual(report['outcome'], 'equal-task-acceptance')
        self.assertEqual(report['accepted_case_delta'], 0)
        self.assertTrue(report['baseline']['all_passed'])
        self.assertTrue(report['stratagent']['all_passed'])
        self.assertFalse(report['labels_attested'])
