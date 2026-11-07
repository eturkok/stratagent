"""Reviewable request coverage and resource necessity; not a semantic quality score."""
import re
from pathlib import PurePosixPath

from .common import StratagentError, identity

MAX_NEEDS = 32
TEXT = {'type': 'string', 'minLength': 3, 'maxLength': 1500}
INDEXES = {'type': 'array', 'maxItems': MAX_NEEDS, 'uniqueItems': True,
           'items': {'type': 'integer', 'minimum': 0, 'maximum': MAX_NEEDS - 1}}
COVERAGE = {'type': 'array', 'minItems': 1, 'maxItems': 32, 'items': {
    'type': 'object', 'additionalProperties': False,
    'required': ['part_id', 'status', 'need_indexes', 'reason'],
    'properties': {'part_id': {'type': 'string', 'maxLength': 200},
                   'status': {'enum': ['covered', 'constraint', 'unknown']},
                   'need_indexes': INDEXES, 'reason': TEXT}}}
JUSTIFICATIONS = {'type': 'array', 'maxItems': 6, 'items': {
    'type': 'object', 'additionalProperties': False,
    'required': ['kind', 'candidate_id', 'need_indexes', 'candidate_quote', 'reason', 'alternative'],
    'properties': {'kind': {'enum': ['skill', 'mcp']},
                   'candidate_id': {'type': 'string', 'minLength': 1, 'maxLength': 200},
                   'option': {'type': 'integer', 'minimum': 0, 'maximum': 39},
                   'need_indexes': {**INDEXES, 'minItems': 1}, 'candidate_quote': {'type': 'string', 'minLength': 3, 'maxLength': 500}, 'reason': TEXT, 'alternative': TEXT}}}


def request_parts(prompt):
    # Text boundaries only: this does not infer requirements or semantic completeness.
    spans = [(m.start(), m.end()) for m in re.finditer(r'[^\n]+', prompt)]
    clauses=[]
    for start, end in spans:
        for match in re.finditer(r'.+?(?:[.!?;](?=\s|$)|$)', prompt[start:end]):
            a, b = start + match.start(), start + match.end()
            while a < b and prompt[a].isspace(): a += 1
            while b > a and prompt[b-1].isspace(): b -= 1
            if a < b: clauses.append((a,b))
    if not clauses:
        clauses=[(0,len(prompt))]
    width=max(1, (len(clauses)+31)//32)
    grouped=[(clauses[i][0], clauses[min(i+width,len(clauses))-1][1]) for i in range(0,len(clauses),width)]
    return [{'id': f'request-part:{i+1}', 'quote': prompt[a:b], 'start': a, 'end': b}
            for i,(a,b) in enumerate(grouped)]


def review_coverage(prompt, needs, coverage):
    parts = {part['id']:part for part in request_parts(prompt)}
    if coverage is None:
        raise StratagentError('The assessment needs coverage for every request part. Reload fit_request and map its request_parts; do not silently omit constraints or needs.')
    if len(coverage) != len(parts) or {item['part_id'] for item in coverage} != set(parts):
        raise StratagentError('Assessment must cover every request part exactly once, including constraints and uncertainty.')
    assigned=set()
    for entry in coverage:
        indexes=entry['need_indexes']
        if any(index >= len(needs) for index in indexes):
            raise StratagentError('Request coverage refers to an unknown assessed need.')
        if entry['status']=='covered':
            if not indexes:
                raise StratagentError('A covered request part must identify its assessed needs.')
            part=parts[entry['part_id']]['quote']
            for index in indexes:
                quote=needs[index]['quote']
                if quote not in part and part not in quote:
                    raise StratagentError('A covered need must quote that actual request part; a generic need cannot stand in for unrelated sentences.')
            assigned.update(indexes)
        elif indexes:
            raise StratagentError('Constraints and unknown request parts cannot claim covered needs.')
    if assigned != set(range(len(needs))):
        raise StratagentError('Every assessed need must be grounded in a covered request part.')
    return [{'quote': parts[entry['part_id']]['quote'], **entry} for entry in coverage]


def review_recommendations(context, assessment, decision):
    """Assessed sessions require one explanation for each selected resource."""
    needs=assessment['needs']
    rows=[]
    selected_skills=set()
    for binding in decision['bindings']:
        expected={('skill', key, 0) for key in binding['skills']}
        expected.update(('mcp', entry['candidate_id'], entry['option']) for entry in binding['mcps'])
        seen=set()
        for justification in binding.get('justifications', []):
            key=(justification['kind'], justification['candidate_id'], justification.get('option',0))
            if key not in expected or key in seen:
                raise StratagentError('Resource explanations must match selected resources exactly once; no unrelated or duplicate explanations.')
            seen.add(key)
            candidates = context['skills'] if key[0] == 'skill' else context.get('mcps', [])
            candidate = next((entry for entry in candidates if entry['id'] == key[1]), None)
            if candidate is None or justification['candidate_quote'] not in candidate.get('description', ''):
                raise StratagentError('Each resource explanation must quote its actual reviewed description; invented capability text is not evidence.')
            indexes=justification['need_indexes']
            if any(index >= len(needs) or needs[index]['status'] not in ('gap','unknown') for index in indexes):
                raise StratagentError('A new resource must address an assessed gap or uncertainty; existing/host coverage alone does not justify another installation.')
            rows.append({'task_id': binding['task_id'], **justification,
                         'needs': [needs[index]['need'] for index in indexes]})
        if seen != expected:
            raise StratagentError('Explain each selected resource: which assessed gap it addresses, why it helps and the alternative, including no addition.')
        selected_skills.update(binding['skills'])
    fingerprints={}
    for candidate in context['skills']:
        if candidate['id'] not in selected_skills or not candidate.get('files'):
            continue
        root = PurePosixPath(candidate.get('entry', 'SKILL.md')).parent
        inventory=[]
        for record in candidate['files']:
            path=PurePosixPath(record['path'])
            relative=str(path.relative_to(root)) if path.is_relative_to(root) else 'notice:' + str(path)
            inventory.append((relative, record['sha256']))
        signature=identity({'kind': candidate.get('kind', 'skill'), 'files': sorted(inventory)})
        if signature in fingerprints:
            raise StratagentError('Two selected skills have identical reviewed file contents. Reuse one instead of installing duplicate bundles; matching content is not a semantic capability score.')
        fingerprints[signature]=candidate['id']
    addressed={index for row in rows for index in row['need_indexes']}
    return {'status': 'assessed', 'resource_explanations': rows,
            'remaining_gaps': [need for index,need in enumerate(needs) if need['status'] in ('gap','unknown') and index not in addressed],
            'note': 'Coverage and reasons remain model judgments for human review. No task-quality score, host capability certification or execution authority is inferred.'}
