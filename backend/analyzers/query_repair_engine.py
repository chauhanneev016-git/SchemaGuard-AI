
import os
import json
import hashlib
from pathlib import Path
from collections import defaultdict

from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
db_name = os.getenv("DATABASE_NAME", "schemaguard_research")

if db_name != "schemaguard_research":
    raise RuntimeError("Unexpected research database.")

client = MongoClient(uri, serverSelectionTimeoutMS=5000)
client.admin.command("ping")
db = client[db_name]

with open(ROOT / "experiments/baseline_v1.json", encoding="utf-8") as f:
    baseline = json.load(f)

def flatten(document, prefix=""):
    result = {}
    for key, value in document.items():
        if key == "_id":
            continue
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(flatten(value, path))
        else:
            result[path] = value
    return result

def get_path(document, path):
    value = document
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return False, None
        value = value[part]
    return True, value

# 1. Match representative V1 and V2 records.
pairs = []

for old in db.students.find().sort("student_id", 1).limit(200):
    new = db.students_v2.find_one(
        {"student_id": old["student_id"]}
    )
    if new is None:
        raise RuntimeError("Missing paired V2 record.")
    pairs.append((flatten(old), flatten(new)))

if not pairs:
    raise RuntimeError("No records available.")

old_fields = set().union(*(a.keys() for a, b in pairs))
new_fields = set().union(*(b.keys() for a, b in pairs))

removed = old_fields - new_fields
added = new_fields - old_fields

# 2. Infer candidate mappings through value preservation.
mapping = {}
confidence = {}

for old_field in sorted(removed):
    candidates = []

    for new_field in sorted(added):
        matches = 0
        compared = 0

        for old, new in pairs:
            if old_field in old and new_field in new:
                compared += 1
                if (
                    type(old[old_field]) is type(new[new_field])
                    and old[old_field] == new[new_field]
                ):
                    matches += 1

        score = matches / compared if compared else 0

        if compared >= 190 and score >= 0.99:
            candidates.append((new_field, score))

    # Only accept unambiguous mappings.
    if len(candidates) == 1:
        mapping[old_field] = candidates[0][0]
        confidence[old_field] = candidates[0][1]

print("\n" + "=" * 60)
print("SCHEMAGUARD AI - AUTOMATIC QUERY REPAIR")
print("=" * 60)

print("\nDISCOVERED FIELD MAPPINGS")

for old, new in mapping.items():
    print(f"  {old} -> {new} ({confidence[old]:.0%} sample match)")

def rewrite_filter(filter_obj):
    rewritten = {}
    for key, value in filter_obj.items():
        new_key = key if key.startswith("$") else mapping.get(key, key)

        if isinstance(value, dict):
            rewritten[new_key] = rewrite_filter(value)
        elif isinstance(value, list):
            rewritten[new_key] = [
                rewrite_filter(v) if isinstance(v, dict) else v
                for v in value
            ]
        else:
            rewritten[new_key] = value
    return rewritten

def fingerprint(data):
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

results_report = []

# 3. Repair queries and compare their semantic outputs.
for test in baseline["tests"]:
    is_students = test["collection"] == "students"

    collection = "students_v2" if is_students else test["collection"]

    query_mapping = mapping if is_students else {}
    new_filter = (
        rewrite_filter(test["filter"])
        if is_students else test["filter"]
    )

    new_sort = query_mapping.get(test["sort"], test["sort"])
    new_fields = [
        query_mapping.get(field, field)
        for field in test["fields"]
    ]

    projection = {field: 1 for field in new_fields}
    projection["_id"] = 0

    documents = list(
        db[collection].find(new_filter, projection).sort(new_sort, 1)
    )

    # Normalize V2 output to V1 field names.
    normalized = []
    missing = []

    for doc in documents:
        record = {}
        for old_field in test["fields"]:
            new_field = query_mapping.get(old_field, old_field)
            exists, value = get_path(doc, new_field)

            if exists:
                record[old_field] = value
            else:
                missing.append(old_field)

        normalized.append(record)

    actual_hash = fingerprint(normalized)
    expected_hash = test["result_fingerprint"]

    restored = (
        actual_hash == expected_hash
        and len(documents) == test["result_count"]
        and not missing
    )

    status = "RESTORED" if restored else "REVIEW_REQUIRED"

    results_report.append({
        "query_id": test["id"],
        "original_filter": test["filter"],
        "repaired_filter": new_filter,
        "expected_count": test["result_count"],
        "actual_count": len(documents),
        "fingerprint_match": actual_hash == expected_hash,
        "missing_fields": sorted(set(missing)),
        "status": status
    })

    print(f"\n{test['id']}: {test['name']}")
    print("  Repaired filter:", new_filter)
    print("  Expected:", test["result_count"])
    print("  Actual:", len(documents))
    print("  Fingerprint match:", actual_hash == expected_hash)
    print("  Status:", status)

# 4. Save research evidence.
output = {
    "method": "paired_document_value_matching",
    "sample_size": len(pairs),
    "field_mappings": mapping,
    "mapping_sample_confidence": confidence,
    "query_results": results_report
}

report_path = ROOT / "experiments/repair_results.json"

with open(report_path, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2)

restored_count = sum(
    r["status"] == "RESTORED" for r in results_report
)

print("\n" + "=" * 60)
print("QUERY REPAIR EXPERIMENT COMPLETED")
print("Queries tested:", len(results_report))
print("Queries restored:", restored_count)
print("Queries needing review:", len(results_report) - restored_count)
print("Report:", report_path)
print("=" * 60)

client.close()
