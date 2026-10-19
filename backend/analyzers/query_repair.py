"""Read-only verification of registered V1 find queries against an evolved collection."""
import json
from pathlib import Path
from fastapi.encoders import jsonable_encoder
from backend.analyzers.field_mapping import discover_mappings

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / 'experiments' / 'baseline_v1.json'
ALLOWED_TARGETS = {'students_v2', 'students_v3'}


def registered_queries():
    if not BASELINE.is_file():
        raise ValueError('Missing experiments/baseline_v1.json')
    payload = json.loads(BASELINE.read_text(encoding='utf-8'))
    return payload['tests']


def query_choices():
    return [{'id': q['id'], 'name': q['name'], 'collection': q['collection'],
             'filter': q['filter'], 'fields': q['fields'], 'expected_count': q['result_count']}
            for q in registered_queries()]


def value_at(doc, path):
    value = doc
    for part in path.split('.'):
        if not isinstance(value, dict) or part not in value:
            return False, None
        value = value[part]
    return True, value


def normalize(field, value):
    if field == 'cgpa' and value is not None:
        try:
            return float(value)
        except (ValueError, TypeError):
            return value
    if field == 'name' and isinstance(value, str):
        return value.strip().casefold()
    return value


def verified_mappings(db, target):
    if target == 'students_v2':
        target_name = 'students_v2'
    elif target == 'students_v3':
        target_name = 'students_v3'
    else:
        raise ValueError('Target must be students_v2 or students_v3')
    report = discover_mappings(db, 'students', target_name, 'student_id', 500)
    mapping = {}
    rejected = []
    for item in report['recommendations']:
        if item['status'] in ('SUGGESTED', 'INCOMPLETE_DATA') and item['validation']['agreement'] >= 0.98:
            mapping[item['source_field']] = item['recommended_field']
        else:
            rejected.append(item['source_field'])
    return mapping, rejected


def rewrite_filter(filters, mapping, target):
    output = {}
    for key, value in filters.items():
        if key == 'cgpa' and target == 'students_v3':
            if not isinstance(value, dict) or set(value) != {'$gte'}:
                raise ValueError('Unsupported numeric filter')
            output['$expr'] = {'$gte': [
                {'$convert': {'input': '$' + mapping.get('cgpa', 'cgpa'),
                              'to': 'double', 'onError': None, 'onNull': None}},
                value['$gte']
            ]}
        elif key in ('department', 'name', 'student_id', 'approved'):
            output[mapping.get(key, key)] = value
        else:
            raise ValueError(f'Unsupported filter field: {key}')
    return output


def verify_query(db, query_id, target):
    if target not in ALLOWED_TARGETS:
        raise ValueError('Unsupported target collection')
    query = next((q for q in registered_queries() if q['id'] == query_id), None)
    if not query:
        raise ValueError('Unknown query ID')

    is_student = query['collection'] == 'students'
    target_collection = target if is_student else query['collection']
    mapping, rejected = verified_mappings(db, target) if is_student else ({}, [])
    necessary = set(query['fields']) | {k for k in query['filter'] if not k.startswith('$')}
    unresolved = sorted(necessary.intersection(rejected))
    if unresolved:
        return {'query_id': query_id, 'target_collection': target_collection,
                'status': 'REVIEW_REQUIRED', 'reason': 'Unresolved field mappings: ' + ', '.join(unresolved),
                'unresolved_fields': unresolved, 'executed': False}

    filters = rewrite_filter(query['filter'], mapping, target)
    projection = {mapping.get(f, f): 1 for f in query['fields']}
    projection['_id'] = 0
    sort_field = mapping.get(query['sort'], query['sort'])
    docs = list(db[target_collection].find(filters, projection).sort(sort_field, 1))
    actual = []
    missing = []
    for row_number, doc in enumerate(docs):
        row = {}
        for field in query['fields']:
            exists, value = value_at(doc, mapping.get(field, field))
            if exists:
                row[field] = value
            else:
                missing.append({'row': row_number, 'field': field})
        actual.append(row)

    expected = query['expected_results']
    exact = actual == expected
    semantic = len(actual) == len(expected) and not missing
    if semantic:
        for a, b in zip(actual, expected):
            for field in query['fields']:
                if field not in a or field not in b or normalize(field, a[field]) != normalize(field, b[field]):
                    semantic = False
                    break
            if not semantic:
                break
    status = 'EXACT_MATCH' if exact else 'SEMANTIC_MATCH' if semantic else 'REVIEW_REQUIRED'
    reason = ('Identical results.' if exact else
              'Results equivalent under registered normalization rules.' if semantic else
              'Missing fields, changed values, or different record membership.')

    return jsonable_encoder({
        'query_id': query_id, 'name': query['name'], 'target_collection': target_collection,
        'executed': True, 'status': status, 'reason': reason,
        'original_filter': query['filter'], 'repaired_filter': filters,
        'original_fields': query['fields'],
        'repaired_fields': {f: mapping.get(f, f) for f in query['fields']},
        'expected_count': len(expected), 'actual_count': len(actual),
        'missing_field_occurrences': len(missing), 'missing_examples': missing[:5],
        'exact_match': exact, 'semantic_match': semantic,
        'expected_preview': expected[:2], 'actual_preview': actual[:2],
        'disclaimer': 'Registered read-only test query, not arbitrary MongoDB execution. Comparison uses a stored V1 baseline and specified normalization rules.'
    })