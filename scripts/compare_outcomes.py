"""Run a paired, offline inventory-CLI acceptance benchmark on reviewed local code.

This explicitly executes each supplied inventory.py in subprocesses. Review those
files first; subprocess isolation flags are not a security sandbox. No model is
launched and no human judgment, development timing or preference is inferred.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def cases():
    valid = [('basic', b'sku,quantity\nA,2\nB,3\n', {'rows': 2, 'total_quantity': 5}),
             ('bom-and-whitespace', b'\xef\xbb\xbfsku,quantity\n A , 0002 \n', {'rows': 1, 'total_quantity': 2}),
             ('zero', b'sku,quantity\nA,0\n', {'rows': 1, 'total_quantity': 0}),
             ('quoted-sku', b'sku,quantity\n"A,B",5\n', {'rows': 1, 'total_quantity': 5})]
    invalid = [('negative', b'sku,quantity\nA,-1\n'), ('fraction', b'sku,quantity\nA,1.5\n'),
               ('plus-sign', b'sku,quantity\nA,+1\n'), ('exponent', b'sku,quantity\nA,1e3\n'),
               ('nan', b'sku,quantity\nA,nan\n'), ('missing-quantity', b'sku,quantity\nA,\n'),
               ('missing-sku', b'sku,quantity\n ,2\n'), ('duplicate', b'sku,quantity\nA,2\n A ,3\n'),
               ('missing-column', b'sku\nA\n'), ('extra-column', b'sku,quantity,secret\nA,2,PRIVATE_MARKER\n'),
               ('extra-field', b'sku,quantity\nA,2,PRIVATE_MARKER\n'), ('short-row', b'sku,quantity\nA\n'),
               ('header-only', b'sku,quantity\n'), ('empty-file', b''),
               ('invalid-utf8', b'sku,quantity\n\xff,2\n'), ('bad-quoting', b'sku,quantity\n"PRIVATE_MARKER,2\n'),
               ('bare-quote', b'sku,quantity\nPRI"VATE_MARKER,2\n'),
               ('missing-file', None)]
    return valid + [(name, data, None) for name, data in invalid]


def evaluate(directory, python):
    program = directory / 'inventory.py'
    code = program.read_bytes()
    readme = (directory / 'README.md').read_bytes()
    results = []
    with tempfile.TemporaryDirectory(prefix='stratagent-task-acceptance-') as temporary:
        for name, data, expected in cases():
            path = Path(temporary) / (name + '.csv')
            if data is not None:
                path.write_bytes(data)
            try:
                process = subprocess.run([python, '-I', '-X', 'utf8', str(program), str(path)],
                                         cwd=temporary, capture_output=True, timeout=10)
                value = json.loads(process.stdout)
                accepted = (process.returncode == (0 if expected is not None else 2) and not process.stderr
                            and (value == expected if expected is not None else
                                 isinstance(value, dict) and isinstance(value.get('error'), str) and bool(value['error'])
                                 and 'PRIVATE_MARKER' not in json.dumps(value)))
            except (subprocess.TimeoutExpired, OSError, ValueError, UnicodeError):
                accepted = False
            if data is not None and (not path.is_file() or path.read_bytes() != data):
                accepted = False
            results.append({'id': name, 'passed': bool(accepted)})
    preserved = program.read_bytes() == code and (directory / 'README.md').read_bytes() == readme
    return {'program_sha256': sha(code), 'task_sha256': sha(readme), 'cases': results,
            'passed': sum(row['passed'] for row in results), 'total': len(results),
            'candidate_and_readme_preserved': preserved,
            'all_passed': all(row['passed'] for row in results) and preserved}


def compare(baseline, assisted, python, host, model):
    if baseline.resolve() == assisted.resolve():
        raise ValueError('Use separate task implementations.')
    if (baseline / 'README.md').read_bytes() != (assisted / 'README.md').read_bytes():
        raise ValueError('Both implementations must have the identical original task.')
    left, right = evaluate(baseline.resolve(), python), evaluate(assisted.resolve(), python)
    delta = right['passed'] - left['passed']
    return {'schema_version': 1, 'benchmark': 'offline-inventory-cli-v1',
            'host_label': host, 'model_label': model, 'labels_attested': False,
            'baseline': left, 'stratagent': right, 'accepted_case_delta': delta,
            'outcome': 'equal-task-acceptance' if delta == 0 else 'assisted-more-cases' if delta > 0 else 'baseline-more-cases',
            'method': 'Maintainer-controlled paired forward test; separate task-local agent runs and fixed executable acceptance.',
            'limitations': ['One task, not a representative corpus or blinded experiment.',
                            'Host/model labels are operator supplied; comparable generation budgets are not enforced.',
                            'No development-time, user-preference, retention or general superiority claim.',
                            'Fixture evaluation subprocess time is not time to implement the task.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--assisted', type=Path, required=True)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--host', required=True, help='Unattested operator label for the coding host')
    parser.add_argument('--model', required=True, help='Unattested operator label; never infer a provider identity')
    parser.add_argument('--output', type=Path, required=True, help='New local report; never overwritten')
    args = parser.parse_args()
    result = compare(args.baseline, args.assisted, args.python, args.host, args.model)
    # Creation is exclusive; a rerun cannot silently replace earlier evidence.
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps({'outcome': result['outcome'], 'baseline': result['baseline']['passed'],
                      'assisted': result['stratagent']['passed'], 'total': result['baseline']['total']}))
    return 0 if result['baseline']['all_passed'] and result['stratagent']['all_passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
