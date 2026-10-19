
import os
import json
from pathlib import Path
from collections import defaultdict

import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DATABASE_NAME", "schemaguard_research")

if DB_NAME != "schemaguard_research":
    raise RuntimeError("Unexpected database.")

def load_json(filename):
    with open(ROOT / "experiments" / filename,
              encoding="utf-8") as f:
        return json.load(f)

benchmark = load_json("expanded_benchmark_1800.json")
workload = load_json("workload_100_v1.json")
manifest = load_json("expanded_scenario_manifest.json")

query_lookup = {q["id"]: q for q in workload["queries"]}
scenario_lookup = {s["id"]: s for s in manifest}

client = MongoClient(URI, serverSelectionTimeoutMS=5000)
client.admin.command("ping")
db = client[DB_NAME]

def get_path(doc, path):
    current = doc
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current

def filter_fields(obj):
    fields = []

    for key, value in obj.items():
        if not key.startswith("$"):
            fields.append(key)

        if isinstance(value, dict):
            fields.extend(filter_fields(value))

    return list(dict.fromkeys(fields))

def field_statistics(pairs, field):
    total = len(pairs)
    missing = 0
    type_changed = 0
    value_changed = 0

    for old, new in pairs:
        old_exists, old_value = get_path(old, field)
        new_exists, new_value = get_path(new, field)

        if old_exists and not new_exists:
            missing += 1

        elif old_exists and new_exists:
            if type(old_value) is not type(new_value):
                type_changed += 1

            if old_value != new_value or (
                type(old_value) is not type(new_value)
            ):
                value_changed += 1

    return {
        "missing": missing / total if total else 0,
        "type_changed": type_changed / total if total else 0,
        "value_changed": value_changed / total if total else 0
    }

print("=" * 65)
print("SCHEMAGUARD AI - ML FEATURE ENGINEERING")
print("=" * 65)

# Build feature statistics using a staging sample.
# No compatibility labels or query outcomes are used here.
scenario_stats = {}

for scenario in manifest:
    old_documents = list(
        db.students.find({}, {"_id": 0})
        .sort("student_id", 1).limit(200)
    )

    new_documents = {
        doc["student_id"]: doc
        for doc in db[scenario["collection"]].find(
            {"student_id": {"$in": [
                old["student_id"] for old in old_documents
            ]}},
            {"_id": 0}
        )
    }

    pairs = []

    for old in old_documents:
        new = new_documents.get(old["student_id"])

        if new is None:
            raise RuntimeError(
                f"Missing record in {scenario['id']}"
            )

        pairs.append((old, new))

    scenario_stats[scenario["id"]] = {
        field: field_statistics(pairs, field)
        for field in [
            "student_id", "name", "phone", "department",
            "cgpa", "semester", "scholarship_type",
            "approved", "amount"
        ]
    }

    print("Sampled:", scenario["id"])

rows = []

for result in benchmark["results"]:
    scenario_id = result["scenario"]
    query = query_lookup[result["query_id"]]

    is_student = query["collection"] == "students"

    used_filter_fields = filter_fields(query["filter"])
    used_projection_fields = query["fields"]

    def summarize(fields, metric):
        if not is_student:
            return 0.0

        values = [
            scenario_stats[scenario_id]
            .get(field, {})
            .get(metric, 0.0)
            for field in fields
        ]

        return max(values) if values else 0.0

    row = {
        "scenario_id": scenario_id,
        "migration_family": result["family"],
        "query_id": result["query_id"],

        # Available prediction features
        "is_student_query": int(is_student),
        "filter_field_count": len(used_filter_fields),
        "projection_field_count": len(used_projection_fields),
        "uses_name": int(
            "name" in used_filter_fields + used_projection_fields
        ),
        "uses_phone": int(
            "phone" in used_filter_fields + used_projection_fields
        ),
        "uses_cgpa": int(
            "cgpa" in used_filter_fields + used_projection_fields
        ),
        "uses_department": int(
            "department" in used_filter_fields + used_projection_fields
        ),
        "filter_missing_rate": summarize(
            used_filter_fields, "missing"
        ),
        "projection_missing_rate": summarize(
            used_projection_fields, "missing"
        ),
        "filter_type_change_rate": summarize(
            used_filter_fields, "type_changed"
        ),
        "projection_type_change_rate": summarize(
            used_projection_fields, "type_changed"
        ),
        "filter_value_change_rate": summarize(
            used_filter_fields, "value_changed"
        ),
        "projection_value_change_rate": summarize(
            used_projection_fields, "value_changed"
        ),

        # Ground-truth label — target, NOT a feature
        "requires_review": result["requires_review"]
    }

    rows.append(row)

df = pd.DataFrame(rows)

output = ROOT / "experiments" / "schemaguard_ml_dataset.csv"
df.to_csv(output, index=False)

print("\n" + "=" * 65)
print("ML DATASET CREATED")
print("=" * 65)

print("Dataset shape:", df.shape)
print("Total samples:", len(df))
print("Feature columns:", 12)
print("\nTarget distribution:")
print(df["requires_review"].value_counts().sort_index())

print("\nMissing values:")
print(df.isnull().sum().sum())

print("\nSaved to:", output)
print("=" * 65)

client.close()
