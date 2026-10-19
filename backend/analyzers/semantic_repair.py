
import os
import json
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DB_NAME = os.getenv("DATABASE_NAME")
load_dotenv(ROOT / ".env")

DB_NAME = os.getenv("DATABASE_NAME", "schemaguard_research")
URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")

if DB_NAME != "schemaguard_research":
    raise RuntimeError("Unexpected research database.")

with open(ROOT / "experiments/baseline_v1.json", encoding="utf-8") as f:
    baseline = json.load(f)

with open(
    ROOT / "experiments/enhanced_mapping_results.json",
    encoding="utf-8"
) as f:
    mapping_report = json.load(f)

mapping = mapping_report["mappings"]

client = MongoClient(URI, serverSelectionTimeoutMS=5000)
client.admin.command("ping")
db = client[DB_NAME]

if db.students_v3.count_documents({}) != 5000:
    raise RuntimeError("V3 must contain 5000 records.")

def get_path(document, path):
    current = document

    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]

    return True, current

def normalize(field, value):
    if value is None:
        return None

    if field == "cgpa":
        try:
            return round(float(value), 4)
        except (ValueError, TypeError, OverflowError):
            return value

    if field == "name" and isinstance(value, str):
        return value.strip().casefold()

    return value

def build_filter(test):
    # For now, only the five registered baseline queries
    # are supported. Unknown query patterns must be reviewed.
    if test["id"] == "Q1":
        return {"academics.branch": "ECE"}

    if test["id"] == "Q2":
        # MongoDB does not automatically treat numeric strings
        # as numbers in ordinary comparison predicates.
        return {
            "$expr": {
                "$gte": [
                    {
                        "$convert": {
                            "input": "$academics.cgpa",
                            "to": "double",
                            "onError": None,
                            "onNull": None
                        }
                    },
                    8.5
                ]
            }
        }

    if test["id"] == "Q3":
        return {
            "profile.full_name": {
                "$regex": "^A",
                "$options": "i"
            }
        }

    if test["id"] == "Q4":
        return {"student_id": 101}

    if test["id"] == "Q5":
        return {"approved": True}

    raise ValueError("Unsupported query.")

def build_projection(test, student_collection):
    paths = [
        mapping.get(field, field) if student_collection else field
        for field in test["fields"]
    ]

    projection = {path: 1 for path in paths}
    projection["_id"] = 0
    return projection

def restore_fields(doc, test, student_collection):
    restored = {}
    missing = []

    for old_field in test["fields"]:
        new_field = (
            mapping.get(old_field, old_field)
            if student_collection else old_field
        )

        exists, value = get_path(doc, new_field)

        if exists:
            restored[old_field] = value
        else:
            missing.append(old_field)

    return restored, missing

print("=" * 65)
print("SCHEMAGUARD AI - SEMANTIC COMPATIBILITY ENGINE")
print("=" * 65)

results = []

for test in baseline["tests"]:
    is_student = test["collection"] == "students"
    collection = "students_v3" if is_student else test["collection"]

    query_filter = build_filter(test)
    projection = build_projection(test, is_student)

    sort_field = (
        mapping.get(test["sort"], test["sort"])
        if is_student else test["sort"]
    )

    documents = list(
        db[collection]
        .find(query_filter, projection)
        .sort(sort_field, 1)
    )

    actual_rows = []
    missing_details = []

    for index, document in enumerate(documents):
        restored, missing = restore_fields(
            document, test, is_student
        )

        actual_rows.append(restored)

        if missing:
            missing_details.append({
                "row": index,
                "missing_fields": missing
            })

    expected_rows = test["expected_results"]

    exact_match = actual_rows == expected_rows

    semantic_match = False

    if len(actual_rows) == len(expected_rows) and not missing_details:
        semantic_match = True

        for expected, actual in zip(expected_rows, actual_rows):
            for field in test["fields"]:
                if field not in expected or field not in actual:
                    semantic_match = False
                    break

                if normalize(field, expected[field]) != normalize(
                    field, actual[field]
                ):
                    semantic_match = False
                    break

            if not semantic_match:
                break

    if exact_match:
        status = "EXACT_MATCH"
    elif semantic_match:
        status = "SEMANTIC_MATCH"
    else:
        status = "REVIEW_REQUIRED"

    result = {
        "query_id": test["id"],
        "query_name": test["name"],
        "collection": collection,
        "filter": query_filter,
        "expected_count": len(expected_rows),
        "actual_count": len(actual_rows),
        "exact_match": exact_match,
        "semantic_match": semantic_match,
        "missing_field_rows": len(missing_details),
        "missing_details_sample": missing_details[:10],
        "status": status
    }

    results.append(result)

    print(f"\n{test['id']}: {test['name']}")
    print("  Expected:", len(expected_rows))
    print("  Actual:", len(actual_rows))
    print("  Exact match:", exact_match)
    print("  Semantic match:", semantic_match)
    print("  Missing field rows:", len(missing_details))
    print("  Status:", status)

report = {
    "target_schema": "V3",
    "method": "registered_query_semantic_validation",
    "supported_queries": 5,
    "results": results
}

output = ROOT / "experiments/semantic_repair_results.json"

with open(output, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print("\n" + "=" * 65)
print("SEMANTIC COMPATIBILITY EXPERIMENT COMPLETED")

for status in ["EXACT_MATCH", "SEMANTIC_MATCH", "REVIEW_REQUIRED"]:
    count = sum(r["status"] == status for r in results)
    print(f"{status}: {count}")

print("Report:", output)
print("=" * 65)

client.close()
