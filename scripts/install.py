"""Install this reviewed checkout in an isolated runtime; never edit shell/host settings.

Uses only the standard library. --wheelhouse installs offline from reviewed local
application/dependency wheels. Otherwise pip obtains the pinned build/runtime
requirements while installing this checkout. No PyPI StratAgent listing is assumed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
try:
    import tomllib
except ImportError:  # Older interpreters can still explain the supported version.
    tomllib = None
import venv
from zipfile import ZipFile, BadZipFile

SOURCE = Path(__file__).resolve().parents[1]
MARKER = 'stratagent-runtime.json'


def source_identity():
    paths = [SOURCE / 'pyproject.toml', *sorted((SOURCE / 'src/stratagent').rglob('*'))]
    files = {str(p.relative_to(SOURCE)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in paths if p.is_file() and p.suffix in ('.py', '.json', '.md', '.toml')}
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def redirected(path):
    if not path.exists() and not path.is_symlink():
        return False
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))


def install(runtime, wheelhouse=None, upgrade=False):
    if sys.version_info < (3, 11):
        raise ValueError('Python 3.11 or newer is required. Select a supported Python interpreter and run this installer again.')
    runtime = Path(runtime).absolute()
    if redirected(runtime):
        raise ValueError('The runtime directory is a redirect. Choose a new physical directory; nothing was replaced.')
    runtime = runtime.parent.resolve() / runtime.name
    version = tomllib.loads((SOURCE / 'pyproject.toml').read_text())['project']['version']
    selected_wheel = None
    if wheelhouse:
        wheelhouse = Path(wheelhouse).resolve(strict=True)
        matches = list(wheelhouse.glob('stratagent_cli-' + version + '-py3-none-any.whl'))
        if len(matches) != 1 or redirected(matches[0]) or not matches[0].is_file():
            raise ValueError('Offline wheelhouse must contain the reviewed application wheel for this checkout version and its compatible dependency wheel.')
        selected_wheel = matches[0]
        expected = {p.relative_to(SOURCE / 'src').as_posix(): p.read_bytes()
                    for p in (SOURCE / 'src/stratagent').rglob('*')
                    if p.is_file() and p.suffix in ('.py', '.json', '.md')}
        try:
            with ZipFile(selected_wheel) as archive:
                actual = [entry for entry in archive.namelist() if entry.startswith('stratagent/')]
                if set(actual) != set(expected) or len(actual) != len(expected):
                    raise ValueError('Offline application wheel differs from this reviewed checkout. Build/select its matching wheel before installing.')
                for name, data in expected.items():
                    if archive.getinfo(name).file_size != len(data) or archive.read(name) != data:
                        raise ValueError('Offline application wheel differs from this reviewed checkout. Preserve it and select the matching reviewed build.')
        except BadZipFile:
            raise ValueError('Offline application wheel is not a valid reviewed wheel archive.') from None
    source = {'version': version, 'identity': source_identity(), 'source': str(SOURCE)}
    if selected_wheel:
        source['wheel_sha256'] = hashlib.sha256(selected_wheel.read_bytes()).hexdigest()
    marker = runtime / MARKER
    python = runtime / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    previous = None
    if runtime.exists():
        if not runtime.is_dir() or redirected(marker) or not marker.is_file() or marker.stat().st_size > 8192:
            raise ValueError('An existing or incomplete runtime was preserved. Choose --runtime NEW_DIRECTORY; this installer never adopts an unmarked environment.')
        try:
            previous = json.loads(marker.read_text())
        except (ValueError, UnicodeError):
            raise ValueError('The runtime receipt is invalid. Preserve it and choose --runtime NEW_DIRECTORY.') from None
        if (not isinstance(previous, dict) or previous.get('installer') != 'stratagent-local-v1'
                or previous.get('runtime') != str(runtime) or not python.is_file()):
            raise ValueError('The runtime receipt does not match this environment. Choose --runtime NEW_DIRECTORY.')
        if previous.get('source') != source and not upgrade:
            raise ValueError('This checkout or wheel changed. Review it, then use --upgrade to update this installer-owned runtime, or choose --runtime NEW_DIRECTORY.')
    else:
        runtime.parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True).create(runtime)
    receipt = {'installer': 'stratagent-local-v1', 'runtime': str(runtime), 'source': source, 'state': 'installing'}
    env = {key: value for key, value in os.environ.items() if key not in ('PYTHONPATH', 'PYTHONHOME')}
    env['PIP_NO_CACHE_DIR'] = '1'
    if not previous or previous.get('state') != 'ready' or upgrade:
        marker.write_text(json.dumps(receipt, indent=2) + '\n')
        command = [str(python), '-m', 'pip', '--disable-pip-version-check', '--no-input', 'install']
        if wheelhouse:
            command += ['--no-index', '--find-links', str(wheelhouse), str(selected_wheel)]
        else:
            command += [str(SOURCE)]
        if upgrade:
            command += ['--upgrade', '--force-reinstall']
        result = subprocess.run(command, cwd=runtime, env=env, capture_output=True, text=True, timeout=240)
        if result.returncode:
            raise ValueError('Package installation failed; the isolated runtime and project were preserved. Check network/index access or provide --wheelhouse with reviewed compatible wheels, then retry.')
    for arguments, expected in [(['-I', '-X', 'utf8', '-m', 'stratagent', '--version'], version), (['-m', 'pip', 'check'], 'No broken requirements found.')]:
        result = subprocess.run([str(python), *arguments], cwd=runtime, env=env, capture_output=True, text=True, timeout=30)
        if result.returncode or result.stdout.strip() != expected:
            raise ValueError('Runtime verification failed. Preserve the environment and rerun with --upgrade after reviewing its package source.')
    receipt['state'] = 'ready'
    marker.write_text(json.dumps(receipt, indent=2) + '\n')
    return {'version': version, 'launcher': [str(python), '-I', '-X', 'utf8', '-m', 'stratagent'],
            'reused': bool(previous and previous.get('state') == 'ready' and not upgrade),
            'global_settings_changed': False, 'project_files_changed': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, default=SOURCE / 'dist/stratagent-runtime')
    parser.add_argument('--wheelhouse', type=Path, help='Offline directory containing reviewed application and dependency wheels')
    parser.add_argument('--upgrade', action='store_true', help='Update only a runtime already owned by this installer')
    parser.add_argument('--workspace', type=Path, default=Path.cwd())
    parser.add_argument('--host', choices=('claude', 'codex', 'antigravity', 'generic'))
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    try:
        if not args.workspace.is_dir():
            raise ValueError('The project directory does not exist. Select an existing project with --workspace.')
        result = install(args.runtime, args.wheelhouse, args.upgrade)
        command = [*result['launcher'], 'setup', '--workspace', str(args.workspace.resolve()), '--json']
        if args.host:
            command += ['--host', args.host]
        env = {key: value for key, value in os.environ.items() if key not in ('PYTHONPATH', 'PYTHONHOME')}
        inspected = subprocess.run(command, env=env, capture_output=True, text=True, timeout=30)
        result['setup'] = json.loads(inspected.stdout)
        if inspected.returncode not in (0, 2):
            raise ValueError('The package installed, but setup inspection failed. Run the returned launcher with doctor.')
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print('StratAgent ' + result['version'] + ' is installed in an isolated runtime. No shell activation is needed.\n')
            print('Tell your coding agent:\nUse StratAgent from this launcher: ' + json.dumps(result['launcher']) +
                  '. Review and connect its first-party instructions to this project' + (' for ' + args.host if args.host else ' for our current coding host') +
                  ', preserving existing files. Then help prepare the project environment.\n')
            print(result['setup']['headline'] + '\n' + result['setup']['summary'])
        return inspected.returncode
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        message = str(error) if isinstance(error, ValueError) else 'Local installation could not complete. Preserve the runtime and check Python, filesystem access and the selected wheelhouse.'
        print(json.dumps({'ok': False, 'error': message}) if args.json else 'StratAgent: ' + message, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
