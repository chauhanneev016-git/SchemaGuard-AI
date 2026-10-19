
import pandas as pd

from pathlib import Path
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix

ROOT = Path(__file__).resolve().parents[1]

df = pd.read_csv(
    ROOT / "experiments/schemaguard_ml_dataset.csv"
)

metadata = [
    "scenario_id",
    "migration_family",
    "query_id"
]

target = "requires_review"

features = [
    col for col in df.columns
    if col not in metadata + [target]
]

df["ml_prediction"] = -1
df["risk_probability"] = 0.0

families = sorted(df["migration_family"].unique())

for family in families:
    train = df["migration_family"] != family
    test = df["migration_family"] == family

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            max_iter=3000,
            class_weight="balanced",
            random_state=42
        )
    )

    model.fit(
        df.loc[train, features],
        df.loc[train, target]
    )

    df.loc[test, "ml_prediction"] = model.predict(
        df.loc[test, features]
    )

    df.loc[test, "risk_probability"] = (
        model.predict_proba(
            df.loc[test, features]
        )[:, 1]
    )

df["error_type"] = "CORRECT"

df.loc[
    (df[target] == 1) &
    (df["ml_prediction"] == 0),
    "error_type"
] = "FALSE_NEGATIVE"

df.loc[
    (df[target] == 0) &
    (df["ml_prediction"] == 1),
    "error_type"
] = "FALSE_POSITIVE"

false_negatives = df[
    df["error_type"] == "FALSE_NEGATIVE"
].copy()

print("=" * 65)
print("SCHEMAGUARD AI - ML ERROR ANALYSIS")
print("=" * 65)

tn, fp, fn, tp = confusion_matrix(
    df[target],
    df["ml_prediction"],
    labels=[0, 1]
).ravel()

print("\nCONFUSION MATRIX")
print("TN:", tn)
print("FP:", fp)
print("FN:", fn)
print("TP:", tp)

print("\nFALSE NEGATIVES BY MIGRATION FAMILY")

print(
    false_negatives
    .groupby("migration_family")
    .size()
    .to_string()
)

print("\nFALSE NEGATIVE FEATURE ANALYSIS")

columns = [
    "scenario_id",
    "query_id",
    "migration_family",
    "uses_phone",
    "uses_cgpa",
    "uses_department",
    "filter_missing_rate",
    "projection_missing_rate",
    "filter_type_change_rate",
    "filter_value_change_rate",
    "projection_value_change_rate",
    "risk_probability"
]

print(
    false_negatives[columns]
    .head(20)
    .to_string(index=False)
)

# Save all held-out predictions and analysis.
output_dir = ROOT / "experiments"

df.to_csv(
    output_dir / "ml_out_of_family_predictions.csv",
    index=False
)

false_negatives.to_csv(
    output_dir / "ml_false_negatives.csv",
    index=False
)

false_positives = df[
    df["error_type"] == "FALSE_POSITIVE"
]

false_positives.to_csv(
    output_dir / "ml_false_positives.csv",
    index=False
)

print("\n" + "=" * 65)
print("ERROR ANALYSIS COMPLETED")
print("False negatives:", len(false_negatives))
print("False positives:", len(false_positives))
print("Reports saved in experiments/")
print("=" * 65)
