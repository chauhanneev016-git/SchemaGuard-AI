
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]

df = pd.read_csv(
    ROOT / "experiments/schemaguard_ml_dataset.csv"
)

target = "requires_review"
metadata = ["scenario_id", "migration_family", "query_id"]
features = [
    c for c in df.columns
    if c not in metadata + [target]
]

X = df[features]
y = df[target]

families = sorted(df["migration_family"].unique())

print("=" * 70)
print("SCHEMAGUARD AI - MACHINE LEARNING EVALUATION")
print("=" * 70)

print("\nDataset shape:", df.shape)
print("Feature count:", len(features))
print("Migration families:", len(families))
print("Positive labels:", int(y.sum()))

def make_models():
    return {
        "Logistic Regression": make_pipeline(
            StandardScaler(),
            LogisticRegression(
                max_iter=3000,
                class_weight="balanced",
                random_state=42
            )
        ),
        "Random Forest": RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            min_samples_leaf=3,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1
        )
    }

predictions = {
    "Logistic Regression": np.zeros(len(df), dtype=int),
    "Random Forest": np.zeros(len(df), dtype=int),
    "Majority Baseline": np.zeros(len(df), dtype=int)
}

fold_reports = []

for family in families:
    test_mask = df["migration_family"] == family
    train_mask = ~test_mask

    X_train = X.loc[train_mask]
    y_train = y.loc[train_mask]
    X_test = X.loc[test_mask]
    y_test = y.loc[test_mask]

    print(f"\n{'-' * 70}")
    print("HELD-OUT FAMILY:", family)
    print("Train samples:", len(X_train))
    print("Test samples:", len(X_test))
    print("Positive test labels:", int(y_test.sum()))

    for name, model in make_models().items():
        model.fit(X_train, y_train)
        pred = model.predict(X_test)

        predictions[name][test_mask.to_numpy()] = pred

        tn, fp, fn, tp = confusion_matrix(
            y_test, pred, labels=[0, 1]
        ).ravel()

        fold_reports.append({
            "family": family,
            "model": name,
            "accuracy": accuracy_score(y_test, pred),
            "precision": precision_score(
                y_test, pred, zero_division=0
            ),
            "recall": recall_score(
                y_test, pred, zero_division=0
            ),
            "f1": f1_score(
                y_test, pred, zero_division=0
            ),
            "TN": int(tn),
            "FP": int(fp),
            "FN": int(fn),
            "TP": int(tp)
        })

        print(
            f"{name:<20} "
            f"F1={f1_score(y_test, pred, zero_division=0):.3f} "
            f"Recall={recall_score(y_test, pred, zero_division=0):.3f} "
            f"FN={fn}"
        )

print("\n" + "=" * 70)
print("OVERALL OUT-OF-FAMILY RESULTS")
print("=" * 70)

overall = {}

for name, pred in predictions.items():
    tn, fp, fn, tp = confusion_matrix(
        y, pred, labels=[0, 1]
    ).ravel()

    overall[name] = {
        "accuracy": float(accuracy_score(y, pred)),
        "precision": float(precision_score(
            y, pred, zero_division=0
        )),
        "recall": float(recall_score(
            y, pred, zero_division=0
        )),
        "f1": float(f1_score(
            y, pred, zero_division=0
        )),
        "TN": int(tn),
        "FP": int(fp),
        "FN": int(fn),
        "TP": int(tp)
    }

    print(f"\n{name}")
    for metric, value in overall[name].items():
        print(f"  {metric}: {value}")

# Save reproducible research results.
output = {
    "evaluation": "leave_one_migration_family_out",
    "feature_names": features,
    "family_count": len(families),
    "overall": overall,
    "per_family": fold_reports
}

report_path = ROOT / "experiments/ml_evaluation_results.json"

with open(report_path, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2)

# Train final models on the available dataset.
# These are for future demonstration, not held-out evaluation.
models_dir = ROOT / "backend" / "models"
models_dir.mkdir(parents=True, exist_ok=True)

for name, model in make_models().items():
    model.fit(X, y)

    filename = (
        "logistic_regression.joblib"
        if name == "Logistic Regression"
        else "random_forest.joblib"
    )

    joblib.dump({
        "model": model,
        "features": features
    }, models_dir / filename)

print("\n" + "=" * 70)
print("TRAINING AND EVALUATION COMPLETE")
print("Evaluation:", report_path)
print("Models saved:", models_dir)
print("=" * 70)
