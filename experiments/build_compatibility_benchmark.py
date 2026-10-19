
import os
import json
import hashlib
from pathlib import Path
from collections import Counter, defaultdict

from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

DB_NAME = os.getenv("DATABASE_NAME", "schemaguard_research")
URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")

if DB_NAME != "schemaguard_research":
    raise RuntimeError("Unexpected database.")

with open(ROOT / "experiments/workload_100_v1.json",
          encoding="utf-8") as f:
    workload = json.load(f)

with open(ROOT / "experiments/scenario_manifest.json",
          encoding="utf-8") as f:
    manifest = json.load(f)

client = MongoClient(URI, serverSelectionTimeoutMS=5000)
client.admin.command("ping")
db = client[DB_NAME]

# Controlled experimental oracle:
# These mappings are KNOWN because we generated the scenarios.
# They must not be used as predictor input during ML training.
SCENARIO_MAPPINGS = {
    "S4": {"name": "identity.legal_name"},
    "S5": {},
    "S6": {},
    "S7": {}
}

def get_path(doc, path):
    value = doc
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return False, None
        value = value[part]
    return True, value

def normalize(field, value):
    if field == "cgpa":
        try:
            return float(value)
        except (ValueError, TypeError):
            return value
    return value

def rewrite_filter(original, scenario, field_map):
    rewritten = {}

    for key, value in original.items():
        new_key = field_map.get(key, key)

        if scenario == "S5" and key == "cgpa":
            if not isinstance(value, dict) or set(value) != {"$gte"}:
                raise ValueError("Unsupported CGPA query")

            rewritten["$expr"] = {
                "$gte": [
                    {
                        "$convert": {
                            "input": "$cgpa",
                            "to": "double",
                            "onError": None,
                            "onNull": None
                        }
                    },
                    value["$gte"]
                ]
            }
        else:
            rewritten[new_key] = value

    return rewritten

def run_query(test, scenario):
    is_student = test["collection"] == "students"
    field_map = SCENARIO_MAPPINGS[scenario] if is_student else {}

    collection_name = (
        manifest[scenario]["collection"]
        if is_student else test["collection"]
    )

    query_filter = rewrite_filter(
        test["filter"], scenario if is_student else "", field_map
    )

    projection = {
        field_map.get(field, field): 1
        for field in test["fields"]
    }
    projection["_id"] = 0

    sort_field = field_map.get(test["sort"], test["sort"])

    documents = list(
        db[collection_name]
        .find(query_filter, projection)
        .sort(sort_field, 1)
    )

    rows = []
    missing_count = 0

    for doc in documents:
        row = {}
        has_missing = False

        for original_field in test["fields"]:
            path = field_map.get(original_field, original_field)
            exists, value = get_path(doc, path)

            if exists:
                row[original_field] = value
            else:
                has_missing = True

        if has_missing:
            missing_count += 1

        rows.append(row)

    return rows, missing_count

def classify(expected, actual, fields):
    if actual == expected:
        return "EXACT_MATCH"

    if len(expected) != len(actual):
        return "REVIEW_REQUIRED"

    for old, new in zip(expected, actual):
        for field in fields:
            if field not in old or field not in new:
                return "REVIEW_REQUIRED"

            if normalize(field, old[field]) != normalize(field, new[field]):
                return "REVIEW_REQUIRED"

    return "SEMANTIC_MATCH"

print("=" * 65)
print("SCHEMAGUARD AI - RESEARCH BENCHMARK")
print("=" * 65)

results = []

for scenario in ["S4", "S5", "S6", "S7"]:
    if db[manifest[scenario]["collection"]].count_documents({}) != 5000:
        raise RuntimeError(f"Incomplete dataset for {scenario}")

    print(f"\nEvaluating {scenario}...")

    for test in workload["queries"]:
        try:
            actual, missing = run_query(test, scenario)

            expected = test["expected_results"]
            status = classify(expected, actual, test["fields"])
            error = None

        except Exception as exc:
            actual = []
            missing = 0
            status = "EXECUTION_ERROR"
            error = str(exc)

        results.append({
            "scenario": scenario,
            "query_id": test["id"],
            "category": test["category"],
            "expected_count": test["expected_count"],
            "actual_count": len(actual),
            "missing_field_rows": missing,
            "status": status,
            "requires_review": int(
                status in ("REVIEW_REQUIRED", "EXECUTION_ERROR")
            ),
            "error": error
        })

    subset = [r for r in results if r["scenario"] == scenario]
    counts = Counter(r["status"] for r in subset)

    print("  EXACT_MATCH:", counts["EXACT_MATCH"])
    print("  SEMANTIC_MATCH:", counts["SEMANTIC_MATCH"])
    print("  REVIEW_REQUIRED:", counts["REVIEW_REQUIRED"])
    print("  EXECUTION_ERROR:", counts["EXECUTION_ERROR"])

summary = Counter(r["status"] for r in results)

report = {
    "method": "controlled_migration_oracle_evaluation",
    "total_evaluations": len(results),
    "scenario_count": 4,
    "query_count": len(workload["queries"]),
    "label_policy": {
        "exact": "identical output after known path mapping",
        "semantic": "CGPA numeric/string equivalence",
        "review": "missing or changed values or membership"
    },
    "summary": dict(summary),
    "results": results
}

output = ROOT / "experiments/compatibility_benchmark_400.json"

with open(output, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print("\n" + "=" * 65)
print("BENCHMARK COMPLETED")
print("Total evaluations:", len(results))
print("Summary:", dict(summary))
print("Review-required cases:", summary["REVIEW_REQUIRED"])
print("Execution errors:", summary["EXECUTION_ERROR"])
print("Report:", output)
print("=" * 65)

client.close()
