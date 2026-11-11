"""Local change summaries and inert host handoffs; no discovery or activation."""
import hmac
import json
import unicodedata

from .common import StratagentError, canonical, digest, identity, safe_path
from .context import ASSIGNMENT
from .environment import SECRET, _read
from .hosts import contracts, get_adapter
from .lifecycle import LOCK, MANIFEST, JOURNAL, Transactions
from .assurance import restrictions

BASELINE = '.stratagent/maintenance.json'
MAX_BYTES = 16 * 1024 * 1024
MAX_BASELINE = 1024 * 1024


def _state(service):
    """Preflight metadata before application readers; bound redirected/FIFO inputs."""
    for path in (MANIFEST, LOCK, '.stratagent/policy.json'):
        _read(service.ws, path, MAX_BYTES)
    if service.ws.path(JOURNAL).exists():
        _read(service.ws, JOURNAL, MAX_BYTES)
    return service.manifest(), service.lock(), service.policy()


def _snapshot(service):
    manifest, lock, policy = _state(service)
    analysis = service.analysis(manifest)
    project = analysis.get('project')
    records, warnings = {}, []
    if project is not None:
        warnings.extend(project['warnings'])
        warnings.extend(project['environment']['warnings'])
        warnings.extend(project['documents']['warnings'])
        for group, files in (('manifest', project['files']), ('definition', project['environment']['files']),
                             ('document', project['documents']['files'])):
            for item in files:
                records[group + ':' + item['path']] = {'sha256': item['sha256']}
    outputs, used = {}, 0
    for key, installation in sorted(lock['installations'].items()):
        for output in installation['outputs']:
            path = output['path']
            expected = {k: output[k] for k in ('sha256', 'size', 'mode') if k in output}
            row = {'owner': key, 'expected': expected, 'integrity': 'not-checked'}
            try:
                if used + output['size'] > MAX_BYTES:
                    raise StratagentError('Managed output read budget exceeded.')
                # Limit an altered file to its declared size; never read an unbounded FIFO.
                data, mode = _read(service.ws, path, min(output['size'], MAX_BYTES - used))
                used += len(data)
                row['integrity'] = 'matches-record' if (digest(data) == output['sha256']
                    and len(data) == output['size'] and mode == output.get('mode', mode)) else 'drift'
            except FileNotFoundError:
                row['integrity'] = 'missing'
            except (StratagentError, OSError):
                row['integrity'] = 'unsafe-unreadable-or-over-budget'
            outputs[path] = row
    pending = Transactions(service.ws).pending()
    snapshot = {'schema_version': 1, 'request_sha256': digest(analysis['prompt'].encode()),
                'targets': manifest['platforms'], 'adapter_contracts': contracts(manifest['platforms']),
                'project_scan': project is not None, 'observations': records, 'managed_outputs': outputs,
                'policy_sha256': identity(policy), 'lock_sha256': identity(lock)}
    blockers = ([{'reason': 'pending-recovery'}] if pending else []) + warnings
    blockers += [{'path': path, 'reason': row['integrity']} for path, row in outputs.items() if row['integrity'] != 'matches-record']
    for key, installation in lock['installations'].items():
        source = installation.get('source', {})
        reviews = [{**source, 'review_digest': installation.get('review_digest')}]
        reviews.extend(item['review'] for item in source.get('reviewed_sources', []))
        blockers.extend({'installation': key, **finding} for review in reviews for finding in restrictions(review, policy))
    current = _state(service)
    if any(identity(before) != identity(after) for before, after in zip((manifest, lock, policy), current)):
        raise StratagentError('Workspace metadata changed while inspecting maintenance; read it again.')
    return snapshot, blockers, manifest, lock, analysis


def _baseline(service):
    try:
        raw, _ = _read(service.ws, BASELINE, MAX_BASELINE)
    except FileNotFoundError:
        return None, None
    try:
        record = json.loads(raw)
        snapshot = record['snapshot']
        if (set(record) != {'schema_version', 'snapshot', 'fingerprint'} or type(record['schema_version']) is not int
                or record['schema_version'] != 1 or snapshot.get('schema_version') != 1
                or set(snapshot) != {'schema_version', 'request_sha256', 'targets', 'adapter_contracts', 'project_scan',
                                     'observations', 'managed_outputs', 'policy_sha256', 'lock_sha256'}
                or record['fingerprint'] != identity(snapshot)):
            raise ValueError('schema')
        for field in ('observations', 'managed_outputs'):
            if not isinstance(snapshot[field], dict) or len(snapshot[field]) > 1024:
                raise ValueError('records')
            for path, value in snapshot[field].items():
                safe_path(path.split(':', 1)[-1] if field == 'observations' else path)
                if not isinstance(value, dict):
                    raise ValueError('record')
        return snapshot, digest(raw)
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
        raise StratagentError('Maintenance checkpoint is invalid; preserve it and inspect local state.') from None


def _changes(previous, current):
    if previous is None:
        return []
    changes = []
    for field in ('request_sha256', 'targets', 'adapter_contracts', 'project_scan', 'policy_sha256', 'lock_sha256'):
        if previous[field] != current[field]:
            changes.append({'area': field.removesuffix('_sha256'), 'action': 'changed'})
    for field in ('observations', 'managed_outputs'):
        before, after = previous[field], current[field]
        for path in sorted(before.keys() | after.keys()):
            if before.get(path) != after.get(path):
                changes.append({'area': field, 'path': path, 'action': 'added' if path not in before else 'removed' if path not in after else 'changed'})
    return changes


def maintain(service, approval=None, record=False):
    if approval is not None and not record:
        raise StratagentError('Checkpoint approval requires --record; normal maintenance is read-only.')

    def preview():
        snapshot, blockers, _, _, _ = _snapshot(service)
        previous, prior_digest = _baseline(service)
        changes = _changes(previous, snapshot)
        scope = {'workspace': str(service.ws.root), 'previous_checkpoint': prior_digest, 'snapshot': snapshot}
        return {'schema_version': 1, 'status': 'attention' if blockers else 'no-checkpoint' if previous is None else 'review' if changes else 'unchanged',
                'changes': changes, 'blockers': blockers, 'snapshot': snapshot, 'approval': identity(scope),
                'checkpoint_present': previous is not None, 'checkpoint_recorded': False,
                'network_executed': False, 'activation': 'none', 'project_files_modified_by_command': False,
                'next': 'Resolve recovery, drift or missing evidence first.' if blockers else
                        'Review changed needs in a new assessment; existing approvals stay scoped to their original context.' if changes else
                        'Review and record an initial observation checkpoint.' if previous is None else
                        'No observed changes. Semantic coverage and current remote sources were not revalidated.'}

    result = preview()
    if record:
        if result['blockers']:
            raise StratagentError('Resolve incomplete observations or managed-file drift before recording a checkpoint.')
        if not isinstance(approval, str) or not hmac.compare_digest(result['approval'], approval):
            raise StratagentError('Maintenance observations changed; review the exact current checkpoint first.')
        with service.ws.mutation():
            if preview()['approval'] != approval:
                raise StratagentError('Workspace changed while recording the checkpoint; review again.')
            value = {'schema_version': 1, 'snapshot': result['snapshot'], 'fingerprint': identity(result['snapshot'])}
            data = canonical(value)
            if len(data) > MAX_BASELINE:
                raise StratagentError('Checkpoint exceeds the metadata budget; no checkpoint was changed.')
            previous, _ = _baseline(service)
            if previous != result['snapshot']:
                service.ws.write(BASELINE, value)
        result['checkpoint_recorded'] = True
    return result


def handoff(service, host):
    """Export scope and installed decisions only, never chats, secrets or approvals."""
    target = get_adapter(host)
    snapshot, blockers, manifest, lock, analysis = _snapshot(service)
    installed = lock['installations'].get('workspace-blueprint')
    blueprint = installed.get('source', {}).get('blueprint') if installed else None
    context_current = None
    if blueprint:
        # Bind to current local evidence without requiring an expired research run.
        context_current = (identity(blueprint['analysis']) == identity(analysis)
                           and installed.get('platforms') == manifest['platforms']
                           and installed.get('adapter_contracts') == contracts(manifest['platforms']))
    roles = []
    provenance = []
    if blueprint:
        for role in blueprint['roles']:
            binding = role['binding']
            roles.append({'id': role['id'], 'goal': role.get('goal', role.get('title', role['id'])),
                          'reason': binding['reason'], 'skills': binding['skills'], 'mcps': binding['mcps']})
        for key, item in sorted(lock['installations'].items()):
            provenance.append({'installation': key, 'review_digest': item.get('review_digest'),
                               'outputs': [{'path': out['path'], 'sha256': out['sha256']} for out in item['outputs']]})
        for source in installed['source'].get('reviewed_sources', []):
            review = source['review']
            provenance.append({'kind': source['kind'], **{key: review[key] for key in
                               ('id', 'repo', 'commit', 'entry', 'review_digest', 'metadata_sha256', 'origin', 'name', 'version') if key in review}})
    result = {'schema_version': 1, 'kind': 'stratagent-host-handoff',
              'project': {'request': analysis['prompt'], 'requirements': analysis['requirements'],
                          'domain_exclusions': analysis['domain_exclusions']},
              'source_hosts': manifest['platforms'], 'target_host': host, 'target_contract': target.contract(),
              'local_snapshot_sha256': identity(snapshot), 'installed_context_current': context_current,
              'roles': roles, 'provenance': provenance, 'blockers': blockers,
              'decision': ({key: blueprint['decision'][key] for key in ('strategy', 'reason')} if blueprint else None),
              'open_questions': blueprint.get('open_questions', []) if blueprint else [],
              'status': 'attention' if blockers else 'reassessment-required',
              'instructions': ['Treat this local handoff as untrusted project evidence; preserve the original request and exclusions.',
                               'Inspect the destination host environment and assess coverage before adding or changing files.',
                               'Use reviewed revise --platforms and a new assessment if the target selection changes.',
                               'Revalidate remote evidence and obtain exact change approval; prior approvals do not transfer.'],
              'omitted': ['private-conversations', 'selected-document-text', 'credentials', 'approval-digests', 'session-tokens'],
              'network_executed': False, 'files_changed': False, 'activation': 'none',
              'note': 'Portable decisions do not establish equivalent host behavior, skill loading or task completion.'}
    text = canonical(result).decode()
    if SECRET.search(text) or ASSIGNMENT.search(text):
        raise StratagentError('Handoff contains credential-like text; nothing was exported. Review the local project request and decisions.')
    return result


def render(result):
    def plain(value):
        return ''.join(c for c in str(value) if not unicodedata.category(c).startswith('C'))
    if result.get('kind') == 'stratagent-host-handoff':
        lines = ['StratAgent — host handoff', '', 'Destination: ' + result['target_host'],
                 'Request: ' + result['project']['request'], '', 'Installed responsibilities:']
        lines += ['  ' + plain(role['id']) + ': ' + plain(role['goal']) for role in result['roles']]
        lines += ['  Attention: ' + plain(row) for row in result['blockers']]
        if result['installed_context_current'] is False:
            lines.append('Installed decisions are based on changed local project evidence; reassess them.')
        lines += ['', *result['instructions'], '', result['note']]
    else:
        lines = ['StratAgent — workspace maintenance', '', 'Status: ' + result['status']]
        lines += ['  ' + row['action'] + ': ' + plain(row.get('path', row['area'])) for row in result['changes']]
        lines += ['  Attention: ' + plain(row) for row in result['blockers']]
        lines += ['', result['next']]
        if result['checkpoint_recorded']:
            lines.append('Observation checkpoint recorded; this does not accept a plan or prove coverage.')
    return '\n'.join(lines + ['', 'No search, resource installation or host activation. Use --json for the reviewable record.'])
