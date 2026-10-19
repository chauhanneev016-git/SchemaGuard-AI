"""SchemaGuard AI v1.0 — research prototype, localhost only."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from backend.analyzers.schema_inspector import compare_schemas
from backend.analyzers.field_mapping import discover_mappings
from backend.analyzers.query_repair import query_choices, verify_query
from backend.analyzers.migration_impact import analyze_migration, TARGETS
from backend.analyzers.advisory_ml import available_scenarios, predict_example
from backend.analyzers.report_pdf import build_report_pdf

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
DB_NAME = os.getenv('DATABASE_NAME', 'schemaguard_research')
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
if DB_NAME != 'schemaguard_research':
    raise RuntimeError('Unexpected database name.')

app = FastAPI(title='SchemaGuard AI', version='1.0.0')
app.add_middleware(CORSMiddleware,
    allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
    allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client[DB_NAME]


def read_report(filename):
    allowed = {'expanded_benchmark_1800.json', 'ml_evaluation_results.json',
               'hybrid_evaluation_results.json'}
    if filename not in allowed:
        raise HTTPException(400, 'Unknown report')
    path = ROOT / 'experiments' / filename
    if not path.is_file():
        raise HTTPException(404, f'Report missing: {filename}')
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        raise HTTPException(500, 'Unable to read report')


class ReviewInput(BaseModel):
    target: str
    query_id: str
    decision: str
    reviewer: str = Field(default='research_operator', min_length=1, max_length=80)
    note: str = Field(default='', max_length=1200)


def audit_rows(target):
    return list(db.schemaguard_reviews.find(
        {'target': target}, {'_id': 0}).sort('created_at', -1).limit(100))


@app.get('/')
def root():
    return {'project': 'SchemaGuard AI', 'version': '1.0.0', 'mode': 'local research prototype'}


@app.get('/api/health')
def health():
    try:
        client.admin.command('ping')
        return {'status': 'connected', 'database': db.name,
                'mongodb_version': client.server_info()['version']}
    except PyMongoError:
        raise HTTPException(503, 'MongoDB unavailable')


@app.get('/api/database/collections')
def collections():
    return {'database': db.name, 'collections': [
        {'name': n, 'documents': db[n].count_documents({})}
        for n in sorted(db.list_collection_names())]}


@app.get('/api/research/benchmark')
def benchmark():
    r = read_report('expanded_benchmark_1800.json')
    return {key: r[key] for key in ('evaluation_count', 'scenario_count', 'summary', 'by_family')}


@app.get('/api/research/ml-results')
def ml_results():
    r = read_report('ml_evaluation_results.json')
    return {'evaluation': r['evaluation'], 'overall': r['overall']}


@app.get('/api/research/hybrid-results')
def hybrid_results():
    return read_report('hybrid_evaluation_results.json')


@app.get('/api/schema/compare')
def schema_compare(source: str = Query(min_length=1), target: str = Query(min_length=1),
                   sample_size: int = Query(default=500, ge=1, le=1000)):
    try:
        return compare_schemas(db, source, target, sample_size)
    except ValueError as error:
        raise HTTPException(400, str(error))


@app.get('/api/schema/mappings')
def schema_mappings(source: str = Query(min_length=1), target: str = Query(min_length=1),
                    join_key: str = 'student_id',
                    sample_size: int = Query(default=500, ge=40, le=1000)):
    try:
        return discover_mappings(db, source, target, join_key, sample_size)
    except ValueError as error:
        raise HTTPException(400, str(error))


@app.get('/api/query/registered')
def registered_query_list():
    try:
        return {'queries': query_choices()}
    except ValueError as error:
        raise HTTPException(400, str(error))


@app.get('/api/query/verify')
def query_verify(query_id: str, target: str = 'students_v3'):
    try:
        return verify_query(db, query_id, target)
    except ValueError as error:
        raise HTTPException(400, str(error))


@app.get('/api/migration/impact')
def migration_impact(target: str = 'students_v3'):
    try:
        return analyze_migration(db, target)
    except ValueError as error:
        raise HTTPException(400, str(error))


@app.get('/api/ml/scenarios')
def ml_scenarios():
    return {'scenarios': available_scenarios(), 'scope': 'historical synthetic benchmark'}


@app.get('/api/ml/predict')
def ml_predict(scenario_id: str, query_id: str):
    try:
        return predict_example(scenario_id, query_id)
    except ValueError as error:
        raise HTTPException(400, str(error))


@app.get('/api/reviews')
def reviews(target: str = 'students_v3'):
    if target not in TARGETS:
        raise HTTPException(400, 'Unsupported target')
    return {'reviews': audit_rows(target)}


@app.post('/api/reviews')
def record_review(data: ReviewInput):
    if data.target not in TARGETS:
        raise HTTPException(400, 'Unsupported target')
    if data.decision not in {'APPROVE_REPAIR', 'REJECT_REPAIR', 'NEEDS_INVESTIGATION'}:
        raise HTTPException(400, 'Invalid review decision')
    if data.query_id not in {item['id'] for item in query_choices()}:
        raise HTTPException(400, 'Unknown registered query')
    # Re-run the registered query to capture evidence at decision time.
    finding = verify_query(db, data.query_id, data.target)
    record = {
        'review_id': str(uuid4()), 'created_at': datetime.now(timezone.utc).isoformat(),
        'target': data.target, 'query_id': data.query_id, 'decision': data.decision,
        'reviewer': data.reviewer.strip(), 'note': data.note.strip(),
        'observed_status': finding['status'], 'executed_migration': False,
    }
    if data.decision == 'APPROVE_REPAIR' and finding['status'] not in {'EXACT_MATCH', 'SEMANTIC_MATCH'}:
        raise HTTPException(409, 'Cannot mark an incompatible query repair approved.')
    db.schemaguard_reviews.insert_one(record.copy())
    return record


@app.get('/api/reports/migration.pdf')
def migration_pdf(target: str = 'students_v3'):
    try:
        report = analyze_migration(db, target)
        pdf_bytes = build_report_pdf(report, audit_rows(target))
        return Response(content=pdf_bytes, media_type='application/pdf', headers={
            'Content-Disposition': f'attachment; filename="SchemaGuard_{target}_Impact.pdf"'
        })
    except ValueError as error:
        raise HTTPException(400, str(error))


@app.get('/api/status')
def status():
    return {'application': 'SchemaGuard AI', 'version': '1.0.0',
            'mode': 'local prototype; human review never executes migration'}