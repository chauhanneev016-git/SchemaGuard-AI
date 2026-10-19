
import os
import json
import hashlib
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
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

def flatten(doc, prefix=""):
    output = {}
    for key, value in doc.items():
        if key == "_id":
            continue
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            output.update(flatten(value, path))
        else:
            output[path] = value
    return output

def get_path(doc, path):
    value = doc
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return False, None
        value = value[part]
    return True, value

def fingerprint(data):
    raw = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()

# Same 200-record discovery sample as V2.
pairs = []
for old in db.students.find().sort("student_id", 1).limit(200):
    new = db.students_v3.find_one({"student_id": old["student_id"]})
    if new is None:
        raise RuntimeError("V3 record missing.")
    pairs.append((flatten(old), flatten(new)))

old_fields = set().union(*(a for a, b in pairs))
new_fields = set().union(*(b for a, b in pairs))

removed = old_fields - new_fields
added = new_fields - old_fields

mapping = {}
ambiguous = {}
unmapped = []

for old_field in sorted(removed):
    candidates = []
    for new_field in sorted(added):
        compared = 0
        matches = 0
        for a, b in pairs:
            if old_field in a and new_field in b:
                compared += 1
                if type(a[old_field]) is type(b[new_field]) and a[old_field] == b[new_field]:
                    matches += 1
        score = matches / compared if compared else 0
        if compared >= 190 and score >= 0.99:
            candidates.append({"field": new_field, "score": score})

    if len(candidates) == 1:
        mapping[old_field] = candidates[0]["field"]
    elif len(candidates) > 1:
        ambiguous[old_field] = candidates
    else:
        unmapped.append(old_field)

print("=" * 60)
print("SCHEMAGUARD AI - V3 BASELINE EVALUATION")
print("=" * 60)

print("\nDISCOVERED MAPPINGS")
for old, new in mapping.items():
    print(f"{old} -> {new}")

print("\nAMBIGUOUS MAPPINGS")
for old, candidates in ambiguous.items():
    print(f"{old}: {[c['field'] for c in candidates]}")

print("\nUNMAPPED FIELDS")
print(unmapped)

# Held-out evaluation against original V1 values.
validation = {}

for old_field, new_field in mapping.items():
    matching = 0
    total = 0
    missing = 0

    for old in db.students.find(
        {"student_id": {"$gt": 200}},
        {"_id": 0}
    ):
        new = db.students_v3.find_one({"student_id": old["student_id"]})
        total += 1

        exists, value = get_path(new, new_field) if new else (False, None)

        if not exists:
            missing += 1
        elif type(value) is type(old.get(old_field)) and value == old.get(old_field):
            matching += 1

    validation[old_field] = {
        "new_field": new_field,
        "matches": matching,
        "total": total,
        "missing": missing,
        "exact_agreement": matching / total if total else 0
    }

# Rewrite only the supported filter structures.
def rewrite_filter(obj):
    rewritten = {}
    for key, value in obj.items():
        new_key = key if key.startswith("$") else mapping.get(key, key)
        if isinstance(value, dict):
            rewritten[new_key] = rewrite_filter(value)
        else:
            rewritten[new_key] = value
    return rewritten

query_results = []

for test in baseline["tests"]:
    is_student = test["collection"] == "students"
    collection_name = "students_v3" if is_student else test["collection"]

    query_filter = rewrite_filter(test["filter"]) if is_student else test["filter"]
    query_fields = [mapping.get(f, f) if is_student else f for f in test["fields"]]
    sort_field = mapping.get(test["sort"], test["sort"]) if is_student else test["sort"]

    projection = {field: 1 for field in query_fields}
    projection["_id"] = 0

    docs = list(
        db[collection_name].find(query_filter, projection).sort(sort_field, 1)
    )

    normalized = []
    for doc in docs:
        row = {}
        for original_field, new_field in zip(test["fields"], query_fields):
            exists, value = get_path(doc, new_field)
            if exists:
                row[original_field] = value
        normalized.append(row)

    matched = (
        len(docs) == test["result_count"]
        and fingerprint(normalized) == test["result_fingerprint"]
    )

    result = {
        "id": test["id"],
        "expected": test["result_count"],
        "actual": len(docs),
        "fingerprint_match": matched,
        "status": "RESTORED" if matched else "FAILED"
    }
    query_results.append(result)

    print(f"\n{test['id']}: {result['status']}")
    print("  Expected:", result["expected"])
    print("  Actual:", result["actual"])
    print("  Exact output match:", matched)

report = {
    "sample_size": 200,
    "target_schema": "V3",
    "mappings": mapping,
    "ambiguous": ambiguous,
    "unmapped": unmapped,
    "held_out_validation": validation,
    "query_results": query_results
}

output = ROOT / "experiments/v3_baseline_results.json"
with open(output, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print("\n" + "=" * 60)
print("V3 EVALUATION COMPLETE")
print("Queries restored:", sum(x["status"] == "RESTORED" for x in query_results), "/ 5")
print("Report saved:", output)
print("=" * 60)

client.close()
