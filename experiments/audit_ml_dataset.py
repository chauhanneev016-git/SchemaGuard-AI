
import json
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parents[1]

path = ROOT / "experiments/compatibility_benchmark_400.json"

with open(path, encoding="utf-8") as f:
    benchmark = json.load(f)

with open(
    ROOT / "experiments/workload_100_v1.json",
    encoding="utf-8"
) as f:
    workload = json.load(f)

rows = benchmark["results"]
query_lookup = {
    q["id"]: q for q in workload["queries"]
}

print("=" * 65)
print("SCHEMAGUARD AI - ML DATASET QUALITY AUDIT")
print("=" * 65)

print("\nDATASET OVERVIEW")
print("Total evaluations:", len(rows))
print("Migration scenarios:", len(set(r["scenario"] for r in rows)))
print("Unique query IDs:", len(set(r["query_id"] for r in rows)))

label_counts = Counter(r["status"] for r in rows)

print("\nCLASS DISTRIBUTION")
for label, count in label_counts.items():
    print(f"{label}: {count} ({count / len(rows) * 100:.2f}%)")

# Detect repeated query definitions.
signatures = defaultdict(list)

for query in workload["queries"]:
    signature = json.dumps({
        "collection": query["collection"],
        "filter": query["filter"],
        "fields": query["fields"],
        "sort": query["sort"]
    }, sort_keys=True)

    signatures[signature].append(query["id"])

duplicates = [
    ids for ids in signatures.values()
    if len(ids) > 1
]

print("\nQUERY DIVERSITY")
print("Unique query definitions:", len(signatures))
print("Repeated query groups:", len(duplicates))
print("Total redundant query entries:",
      sum(len(ids) - 1 for ids in duplicates))

print("\nSCENARIO-WISE REVIEW LABELS")

for scenario in sorted(set(r["scenario"] for r in rows)):
    subset = [r for r in rows if r["scenario"] == scenario]
    review = sum(r["requires_review"] for r in subset)
    print(f"{scenario}: {review}/{len(subset)} require review")

# A trivial classifier predicts all cases as compatible.
positive = sum(r["requires_review"] for r in rows)
negative = len(rows) - positive

majority_accuracy = max(positive, negative) / len(rows)

print("\nMAJORITY-CLASS BASELINE")
print(f"Accuracy: {majority_accuracy:.2%}")
print("Breaking-change recall: 0.00%")
print("Warning: accuracy alone is misleading.")

report = {
    "total_evaluations": len(rows),
    "scenario_count": len(set(r["scenario"] for r in rows)),
    "unique_query_definitions": len(signatures),
    "duplicate_query_groups": duplicates,
    "class_distribution": dict(label_counts),
    "majority_baseline_accuracy": majority_accuracy,
    "recommendation": (
        "Expand independent migration families and use "
        "scenario-grouped train/test evaluation."
    )
}

output = ROOT / "experiments/ml_dataset_audit.json"

with open(output, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print("\nAudit saved:", output)
print("=" * 65)
