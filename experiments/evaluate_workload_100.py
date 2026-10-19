
import os
import json
from pathlib import Path
from collections import Counter

from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DATABASE_NAME", "schemaguard_research")

if DB_NAME != "schemaguard_research":
    raise RuntimeError("Unexpected database.")

with open(ROOT / "experiments/workload_100_v1.json",
          encoding="utf-8") as f:
    workload = json.load(f)

with open(ROOT / "experiments/enhanced_mapping_results.json",
          encoding="utf-8") as f:
    mapping = json.load(f)["mappings"]

client = MongoClient(URI, serverSelectionTimeoutMS=5000)
client.admin.command("ping")
db = client[DB_NAME]

assert db.students_v3.count_documents({}) == 5000

def get_path(doc, path):
    current = doc
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current

def normalize(field, value):
    if field == "cgpa":
        try:
            return float(value)
        except (TypeError, ValueError):
            return value

    if field == "name" and isinstance(value, str):
        return value.strip().casefold()

    return value

def rewrite_filter(original, is_student):
    if not is_student:
        return original

    rewritten = {}

    for key, value in original.items():
        new_key = mapping.get(key, key)

        if key == "cgpa" and isinstance(value, dict):
            if set(value) == {"$gte"}:
                rewritten["$expr"] = {
                    "$gte": [
                        {
                            "$convert": {
                                "input": "$academics.cgpa",
                                "to": "double",
                                "onError": None,
                                "onNull": None
                            }
                        },
                        value["$gte"]
                    ]
                }
            else:
                raise ValueError("Unsupported CGPA filter")

        elif key in ("department", "name", "student_id",
                     "semester"):
            rewritten[new_key] = value

        else:
            raise ValueError(f"Unsupported filter: {key}")

    return rewritten

def extract_rows(documents, fields, is_student):
    rows = []
    missing_rows = 0

    for doc in documents:
        row = {}
        has_missing = False

        for field in fields:
            path = mapping.get(field, field) if is_student else field
            exists, value = get_path(doc, path)

            if exists:
                row[field] = value
            else:
                has_missing = True

        rows.append(row)
        if has_missing:
            missing_rows += 1

    return rows, missing_rows

def semantic_equal(expected, actual, fields):
    if len(expected) != len(actual):
        return False

    for old, new in zip(expected, actual):
        for field in fields:
            if field not in old or field not in new:
                return False

            if normalize(field, old[field]) != normalize(
                field, new[field]
            ):
                return False

    return True

print("=" * 65)
print("SCHEMAGUARD AI - 100 QUERY COMPATIBILITY EVALUATION")
print("=" * 65)

results = []

for test in workload["queries"]:
    is_student = test["collection"] == "students"
    collection = "students_v3" if is_student else test["collection"]

    try:
        new_filter = rewrite_filter(test["filter"], is_student)

        projection = {
            mapping.get(field, field) if is_student else field: 1
            for field in test["fields"]
        }
        projection["_id"] = 0

        sort_field = (
            mapping.get(test["sort"], test["sort"])
            if is_student else test["sort"]
        )

        documents = list(
            db[collection]
            .find(new_filter, projection)
            .sort(sort_field, 1)
        )

        actual, missing = extract_rows(
            documents, test["fields"], is_student
        )

        expected = test["expected_results"]
        exact = actual == expected

        semantic = (
            missing == 0
            and semantic_equal(expected, actual, test["fields"])
        )

        if exact:
            status = "EXACT_MATCH"
        elif semantic:
            status = "SEMANTIC_MATCH"
        else:
            status = "REVIEW_REQUIRED"

        error = None

    except Exception as exc:
        status = "EXECUTION_ERROR"
        actual = []
        missing = 0
        error = str(exc)

    results.append({
        "query_id": test["id"],
        "category": test["category"],
        "expected_count": test["expected_count"],
        "actual_count": len(actual),
        "missing_field_rows": missing,
        "status": status,
        "error": error
    })

    print(
        f"{test['id']} | "
        f"{test['category']:<12} | "
        f"{status}"
    )

counts = Counter(r["status"] for r in results)

print("\n" + "=" * 65)
print("FINAL COMPATIBILITY SUMMARY")
print("=" * 65)

for status in [
    "EXACT_MATCH", "SEMANTIC_MATCH",
    "REVIEW_REQUIRED", "EXECUTION_ERROR"
]:
    print(f"{status}: {counts[status]}")

print("\nRESULTS BY CATEGORY")
for category in ["department", "cgpa", "name",
                 "contact", "scholarship"]:
    subset = [r for r in results if r["category"] == category]
    category_counts = Counter(r["status"] for r in subset)
    print(f"{category}: {dict(category_counts)}")

report = {
    "experiment": "100_query_v3_compatibility",
    "total_queries": len(results),
    "summary": dict(counts),
    "results": results
}

output = ROOT / "experiments/workload_100_results.json"

with open(output, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print("\nReport saved:", output)
print("=" * 65)

client.close()
