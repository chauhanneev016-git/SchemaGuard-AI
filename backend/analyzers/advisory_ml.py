"""Advisory classifier on precomputed experimental feature rows only.

No prospective risk estimate is made for an arbitrary live migration.
"""
import json
from pathlib import Path
import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / 'experiments' / 'schemaguard_ml_dataset.csv'
MODEL = ROOT / 'backend' / 'models' / 'logistic_regression.joblib'


def available_scenarios():
    if not DATASET.exists():
        return []
    df = pd.read_csv(DATASET, usecols=['scenario_id'])
    return sorted(df['scenario_id'].unique().tolist())


def predict_example(scenario_id, query_id):
    if not MODEL.is_file() or not DATASET.is_file():
        raise ValueError('ML model or feature dataset missing; train Step 22 first.')
    df = pd.read_csv(DATASET)
    subset = df[(df['scenario_id'] == scenario_id) & (df['query_id'] == query_id)]
    if len(subset) != 1:
        raise ValueError('Choose a valid benchmark scenario and query ID.')
    bundle = joblib.load(MODEL)  # Only load locally created trusted files.
    required = bundle['features']
    missing = set(required) - set(subset.columns)
    if missing:
        raise ValueError('Feature dataset does not match the trained model.')
    x = subset[required]
    prob = float(bundle['model'].predict_proba(x)[0][1])
    return {
        'scenario_id': scenario_id, 'query_id': query_id,
        'risk_score': round(prob, 4),
        'flagged_at_0_5': prob >= 0.5,
        'actual_benchmark_label': int(subset.iloc[0]['requires_review']),
        'model': 'Logistic Regression (trained on synthetic benchmark)',
        'scope': 'Historical benchmark row only; not a live migration prediction.',
        'warning': 'The model was trained on these experimental families; this score is not an independent evaluation or migration authorization.'
    }