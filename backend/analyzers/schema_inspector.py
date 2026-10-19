from collections import defaultdict
from datetime import datetime
from bson import ObjectId


def value_type(value):
    if value is None: return 'null'
    if isinstance(value, bool): return 'boolean'
    if isinstance(value, str): return 'string'
    if isinstance(value, int): return 'integer'
    if isinstance(value, float): return 'double'
    if isinstance(value, datetime): return 'datetime'
    if isinstance(value, ObjectId): return 'objectId'
    if isinstance(value, list): return 'array'
    if isinstance(value, dict): return 'object'
    return type(value).__name__


def flatten_document(doc, prefix=''):
    fields = {}
    for key, value in doc.items():
        if key == '_id' and not prefix:
            continue
        path = f'{prefix}.{key}' if prefix else key
        if isinstance(value, dict):
            fields[path] = 'object'
            fields.update(flatten_document(value, path))
        else:
            fields[path] = value_type(value)
    return fields


def inspect_collection(db, name, sample_size=500):
    if name not in db.list_collection_names():
        raise ValueError(f'Collection not found: {name}')
    collection = db[name]
    total = collection.count_documents({})
    stats = defaultdict(lambda: {'present': 0, 'types': defaultdict(int)})
    sampled = 0
    for doc in collection.find({}).sort('_id', 1).limit(sample_size):
        sampled += 1
        for path, typ in flatten_document(doc).items():
            stats[path]['present'] += 1
            stats[path]['types'][typ] += 1
    return {
        'collection': name, 'total_documents': total,
        'sampled_documents': sampled, 'sampling_method': 'first_documents_by_id',
        'fields': {path: {'present': info['present'],
                          'coverage': round(info['present'] / sampled, 4) if sampled else 0,
                          'types': dict(info['types'])}
                   for path, info in sorted(stats.items())}
    }


def compare_schemas(db, source, target, sample_size=500):
    if source == target:
        raise ValueError('Choose two different collections.')
    old = inspect_collection(db, source, sample_size)
    new = inspect_collection(db, target, sample_size)
    a, b = old['fields'], new['fields']
    added = sorted(set(b) - set(a))
    removed = sorted(set(a) - set(b))
    types, coverage = [], []
    for path in sorted(set(a) & set(b)):
        at, bt = sorted(a[path]['types']), sorted(b[path]['types'])
        if at != bt:
            types.append({'field': path, 'source_types': at, 'target_types': bt})
        if a[path]['coverage'] != b[path]['coverage']:
            coverage.append({'field': path, 'source_coverage': a[path]['coverage'],
                             'target_coverage': b[path]['coverage']})
    return {'source': old, 'target': new,
            'summary': {'added_fields': len(added), 'removed_fields': len(removed),
                        'type_changes': len(types), 'coverage_changes': len(coverage)},
            'changes': {'added': added, 'removed': removed, 'type_changes': types,
                        'coverage_changes': coverage},
            'warning': 'Sample-based analysis; renames and compatibility are not established.'}