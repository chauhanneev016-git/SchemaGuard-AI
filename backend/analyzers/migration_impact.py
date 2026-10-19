"""Batch verification and evidence-based migration recommendations."""
from collections import Counter
from datetime import datetime, timezone
from backend.analyzers.query_repair import query_choices, verify_query

TARGETS = {'students_v2', 'students_v3'}


def recommendations_for(item):
    status = item['status']
    if status == 'EXACT_MATCH':
        return ['No query rewrite needed for this registered test.']
    if status == 'SEMANTIC_MATCH':
        return ['Preserve the verified field mappings in a versioned compatibility adapter.',
                'Retest on fresh data and additional application workloads before deployment.']
    if status == 'EXECUTION_ERROR':
        return ['Resolve the execution error and rerun the affected query before review.']
    actions = ['Block automatic migration approval for this query.',
               'Inspect affected source and target records and validate data recovery options.']
    if item.get('missing_fields', 0):
        actions.append('Restore missing values from a trusted backup or obtain authorized corrections; renaming cannot recover data.')
    if item.get('unresolved_fields'):
        actions.append('Manually resolve ambiguous or unverified mappings.')
    return actions


def analyze_migration(db, target):
    if target not in TARGETS:
        raise ValueError('Target must be students_v2 or students_v3.')
    if target not in db.list_collection_names():
        raise ValueError('Target collection was not found.')
    output = []
    for query in query_choices():
        try:
            result = verify_query(db, query['id'], target)
            entry = {
                'query_id': query['id'], 'query_name': query['name'],
                'status': result['status'], 'executed': result.get('executed', False),
                'reason': result.get('reason', ''), 'original_filter': query['filter'],
                'repaired_filter': result.get('repaired_filter'),
                'field_mappings': result.get('repaired_fields', {}),
                'expected_count': result.get('expected_count', query.get('expected_count')),
                'actual_count': result.get('actual_count'),
                'missing_fields': result.get('missing_field_occurrences', 0),
                'missing_examples': result.get('missing_examples', []),
                'unresolved_fields': result.get('unresolved_fields', []),
            }
        except Exception as exc:
            entry = {
                'query_id': query['id'], 'query_name': query['name'],
                'status': 'EXECUTION_ERROR', 'executed': False,
                'reason': f'{type(exc).__name__}: {exc}',
                'original_filter': query['filter'], 'repaired_filter': None,
                'field_mappings': {}, 'expected_count': query.get('expected_count'),
                'actual_count': None, 'missing_fields': 0,
                'missing_examples': [], 'unresolved_fields': [],
            }
        entry['recommendations'] = recommendations_for(entry)
        output.append(entry)
    counts = Counter(row['status'] for row in output)
    total = len(output)
    passed = counts['EXACT_MATCH'] + counts['SEMANTIC_MATCH']
    decision = ('ANALYSIS_INCOMPLETE' if counts['EXECUTION_ERROR'] else
                'REVIEW_REQUIRED' if counts['REVIEW_REQUIRED'] else
                'REGISTERED_TESTS_PASSED')
    return {
        'project': 'SchemaGuard AI', 'version': '1.0',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'database': db.name, 'source_schema': 'students', 'target_schema': target,
        'summary': {
            'total_queries': total, 'exact_match': counts['EXACT_MATCH'],
            'semantic_match': counts['SEMANTIC_MATCH'],
            'review_required': counts['REVIEW_REQUIRED'],
            'execution_errors': counts['EXECUTION_ERROR'],
            'compatible_queries': passed,
            'compatibility_rate': round(passed / total * 100, 2) if total else 0,
            'decision': decision,
        },
        'queries': output,
        'limitations': [
            'Only five registered queries are checked, not arbitrary workloads.',
            'Mappings are heuristic and use paired synthetic records.',
            'Passing tests does not certify a production migration.',
            'No source or target documents are modified.',
            'Human review records an opinion only; it does not execute a migration.'
        ],
    }