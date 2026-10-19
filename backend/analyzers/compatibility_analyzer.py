
import os
import json
import hashlib
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DATABASE_NAME", "schemaguard_research")

if DB_NAME != "schemaguard_research":
    raise ValueError("Unexpected database name.")

baseline_path = ROOT / "experiments" / "baseline_v1.json"

with open(baseline_path, encoding="utf-8") as f:
    baseline = json.load(f)

client = MongoClient(URI, serverSelectionTimeoutMS=5000)
client.admin.command("ping")
db = client[DB_NAME]

if db.students_v2.count_documents({}) != 5000:
    raise RuntimeError("Expected 5000 V2 student documents.")

def fingerprint(data):
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

def get_field(document, field):
    current = document
    for part in field.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current

report = []

print("\n" + "=" * 65)
print("SCHEMAGUARD AI - SCHEMA COMPATIBILITY ANALYZER")
print("=" * 65)

for test in baseline["tests"]:

    collection_name = (
        "students_v2"
        if test["collection"] == "students"
        else test["collection"]
    )

    projection = {field: 1 for field in test["fields"]}
    projection["_id"] = 0

    current_results = list(
        db[collection_name]
        .find(test["filter"], projection)
        .sort(test["sort"], 1)
    )

    old_results = test["expected_results"]

    count_match = len(current_results) == test["result_count"]

    current_hash = fingerprint(current_results)
    output_match = current_hash == test["result_fingerprint"]

    missing_fields = set()

    for doc in current_results:
        for field in test["fields"]:
            found, _ = get_field(doc, field)
            if not found:
                missing_fields.add(field)

    if output_match:
        status = "COMPATIBLE"
    elif not count_match:
        status = "BREAKING_CHANGE"
    else:
        status = "OUTPUT_MISMATCH"

    result = {
        "query_id": test["id"],
        "query_name": test["name"],
        "collection": collection_name,
        "expected_count": test["result_count"],
        "actual_count": len(current_results),
        "count_match": count_match,
        "output_match": output_match,
        "missing_fields": sorted(missing_fields),
        "status": status
    }

    report.append(result)

    print(f"\n{test['id']}: {test['name']}")
    print("  Expected:", test["result_count"])
    print("  Actual:", len(current_results))
    print("  Missing fields:", sorted(missing_fields))
    print("  Status:", status)

output_path = ROOT / "experiments" / "compatibility_v1_to_v2.json"

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

compatible = sum(r["status"] == "COMPATIBLE" for r in report)
breaking = len(report) - compatible

print("\n" + "=" * 65)
print("COMPATIBILITY ANALYSIS COMPLETED")
print("Queries analyzed:", len(report))
print("Compatible queries:", compatible)
print("Incompatible queries:", breaking)
print("Report saved:", output_path)
print("=" * 65)

client.close()
