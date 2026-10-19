"""Read-only, paired-document field-mapping suggestions for research collections."""
import math
from difflib import SequenceMatcher
from pymongo import ASCENDING


def flatten(doc, prefix=''):
    result = {}
    for k, v in doc.items():
        if k == '_id' and not prefix:
            continue
        path = f'{prefix}.{k}' if prefix else k
        if isinstance(v, dict):
            result.update(flatten(v, path))
        elif not isinstance(v, list):
            result[path] = v
    return result


def normalize(value):
    if isinstance(value, bool): return ('bool', value)
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return ('number', round(float(value), 6))
    if isinstance(value, str):
        s = value.strip()
        try:
            n = float(s)
            if math.isfinite(n): return ('number', round(n, 6))
        except ValueError:
            pass
        return ('text', s.casefold())
    if value is None: return ('null', None)
    return (type(value).__name__, str(value))


def name_similarity(a, b):
    a = a.split('.')[-1].lower().replace('_', '')
    b = b.split('.')[-1].lower().replace('_', '')
    return SequenceMatcher(None, a, b).ratio()


def score(pairs, old_field, new_field):
    available = matched = 0
    for old, new in pairs:
        if old_field in old and new_field in new:
            available += 1
            if normalize(old[old_field]) == normalize(new[new_field]):
                matched += 1
    coverage = available / len(pairs) if pairs else 0
    agreement = matched / available if available else 0
    lexical = name_similarity(old_field, new_field)
    # Penalize fields that exist only on a minority of records.
    combined = .75 * agreement * coverage + .20 * coverage + .05 * lexical
    return {'path': new_field, 'score': round(combined, 4),
            'agreement': round(agreement, 4), 'coverage': round(coverage, 4),
            'name_similarity': round(lexical, 4)}


def discover_mappings(db, source, target, join_key='student_id', sample_size=500):
    if source == target: raise ValueError('Choose different collections.')
    if source not in db.list_collection_names() or target not in db.list_collection_names():
        raise ValueError('One or both collections do not exist.')
    if not join_key or join_key.startswith('$') or '.' in join_key:
        raise ValueError('Join key must be a simple field name.')
    if not 40 <= sample_size <= 1000: raise ValueError('Sample size must be 40–1000.')
    original = list(db[source].find({join_key: {'$exists': True}})
                    .sort(join_key, ASCENDING).limit(sample_size))
    keys = [d[join_key] for d in original]
    if len(keys) != len(set(keys)):
        raise ValueError('Source join key is not unique in sample.')
    lookup = {}
    for doc in db[target].find({join_key: {'$in': keys}}):
        key = doc[join_key]
        if key in lookup: raise ValueError('Duplicate target join key.')
        lookup[key] = doc
    pairs = [(flatten(old), flatten(lookup[old[join_key]]))
             for old in original if old[join_key] in lookup]
    if len(pairs) < 40: raise ValueError('At least 40 paired records are required.')
    split = max(20, min(int(len(pairs) * .60), len(pairs) - 10))
    training, heldout = pairs[:split], pairs[split:]
    old_paths = set().union(*(a.keys() for a, _ in training))
    new_paths = set().union(*(b.keys() for _, b in training))
    removed = sorted(old_paths - new_paths)
    added = sorted(new_paths - old_paths)
    recommendations = []
    for old_field in removed:
        candidates = sorted((score(training, old_field, field) for field in added),
                            key=lambda x: x['score'], reverse=True)
        top = candidates[:3]
        best = top[0] if top else None
        if not best or best['agreement'] < .8 or best['coverage'] < .5:
            status = 'LOW_CONFIDENCE'
        elif len(top) > 1 and top[1]['score'] >= best['score'] - .08 and top[1]['agreement'] >= .8:
            status = 'AMBIGUOUS'
        elif best['coverage'] < .8:
            status = 'INCOMPLETE_DATA'
        else:
            status = 'SUGGESTED'
        validation = score(heldout, old_field, best['path']) if best else {
            'path': None, 'score': 0, 'agreement': 0, 'coverage': 0, 'name_similarity': 0}
        validation['records'] = len(heldout)
        if best and validation['agreement'] < .8:
            status = 'VALIDATION_FAILED'
        elif best and validation['coverage'] < .999 and status == 'SUGGESTED':
            status = 'INCOMPLETE_DATA'
        warnings = []
        if best and validation['coverage'] < .999:
            warnings.append('Some target documents lack this field; values cannot be recovered by renaming.')
        if status == 'AMBIGUOUS': warnings.append('Multiple plausible fields; manual confirmation required.')
        if status == 'VALIDATION_FAILED': warnings.append('Insufficient held-out value agreement.')
        if status == 'LOW_CONFIDENCE': warnings.append('Insufficient evidence; do not apply automatically.')
        recommendations.append({'source_field': old_field,
                                'recommended_field': best['path'] if best else None,
                                'status': status, 'candidates': top,
                                'validation': validation, 'warnings': warnings})
    return {'source': source, 'target': target, 'join_key': join_key,
            'matched_records': len(pairs), 'discovery_records': len(training),
            'validation_records': len(heldout), 'recommendations': recommendations,
            'disclaimer': 'Heuristic scores, not calibrated probabilities. Read-only suggestions, not approved migrations.'}