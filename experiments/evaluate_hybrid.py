
from pathlib import Path
import json

import numpy as np
import pandas as pd

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "experiments/ml_out_of_family_predictions.csv"

df = pd.read_csv(DATA)

required_columns = [
    "requires_review",
    "ml_prediction",
    "migration_family",
    "uses_phone",
    "uses_cgpa",
    "uses_department",
    "filter_missing_rate",
    "projection_missing_rate",
    "filter_type_change_rate",
    "projection_type_change_rate",
    "filter_value_change_rate",
    "projection_value_change_rate"
]

missing = set(required_columns) - set(df.columns)
if missing:
    raise ValueError(f"Missing columns: {missing}")

if len(df) != 1800:
    raise ValueError("Expected 1800 observations.")

# Fixed rule-based risk checks.
# Only precomputed sampling features are used.
def safety_rule(row):
    # Potential information loss in a queried field.
    missing_risk = (
        row["filter_missing_rate"] > 0
        or row["projection_missing_rate"] > 0
    )

    # Department value changed, not merely relocated.
    department_risk = (
        row["uses_department"] == 1
        and (
            row["filter_value_change_rate"] > 0
            or row["projection_value_change_rate"] > 0
        )
    )

    # CGPA values changed beyond type representation alone.
    cgpa_risk = (
        row["uses_cgpa"] == 1
        and (
            row["filter_value_change_rate"]
            > row["filter_type_change_rate"] + 1e-9
            or row["projection_value_change_rate"]
            > row["projection_type_change_rate"] + 1e-9
        )
    )

    return int(
        missing_risk or department_risk or cgpa_risk
    )

df["rule_prediction"] = df.apply(safety_rule, axis=1)

# Hybrid flags a case if either component flags it.
df["hybrid_prediction"] = (
    (df["ml_prediction"] == 1)
    | (df["rule_prediction"] == 1)
).astype(int)

y = df["requires_review"].astype(int)

def evaluate(pred):
    tn, fp, fn, tp = confusion_matrix(
        y, pred, labels=[0, 1]
    ).ravel()

    return {
        "accuracy": round(accuracy_score(y, pred), 4),
        "precision": round(
            precision_score(y, pred, zero_division=0), 4
        ),
        "recall": round(
            recall_score(y, pred, zero_division=0), 4
        ),
        "f1": round(
            f1_score(y, pred, zero_division=0), 4
        ),
        "TN": int(tn),
        "FP": int(fp),
        "FN": int(fn),
        "TP": int(tp)
    }

results = {
    "Logistic Regression": evaluate(df["ml_prediction"]),
    "Safety Rules": evaluate(df["rule_prediction"]),
    "Hybrid": evaluate(df["hybrid_prediction"])
}

print("=" * 65)
print("SCHEMAGUARD AI - HYBRID RISK EVALUATION")
print("=" * 65)

for name, metrics in results.items():
    print(f"\n{name}")
    for key, value in metrics.items():
        print(f"  {key}: {value}")

print("\nMISSED RISKS BY FAMILY")

for family, subset in df.groupby("migration_family"):
    actual_risk = subset["requires_review"] == 1

    ml_missed = int((
        actual_risk & (subset["ml_prediction"] == 0)
    ).sum())

    rule_missed = int((
        actual_risk & (subset["rule_prediction"] == 0)
    ).sum())

    hybrid_missed = int((
        actual_risk & (subset["hybrid_prediction"] == 0)
    ).sum())

    print(
        f"{family:<26} "
        f"ML: {ml_missed:3d} | "
        f"Rules: {rule_missed:3d} | "
        f"Hybrid: {hybrid_missed:3d}"
    )

output_dir = ROOT / "experiments"

df.to_csv(
    output_dir / "hybrid_predictions.csv",
    index=False
)

with open(
    output_dir / "hybrid_evaluation_results.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(results, f, indent=2)

print("\n" + "=" * 65)
print("HYBRID EXPERIMENT COMPLETE")
print("Results saved in experiments/")
print("=" * 65)
