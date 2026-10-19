
import os
import json
import math
from pathlib import Path

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

def flatten(doc, prefix=""):
    result = {}
    for key, value in doc.items():
        if key == "_id":
            continue
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(flatten(value, path))
        else:
            result[path] = value
    return result

def normalize(value):
    if isinstance(value, bool):
        return ("bool", value)

    if isinstance(value, (int, float)):
        number = float(value)
        if math.isfinite(number):
            return ("number", number)

    if isinstance(value, str):
        stripped = value.strip()

        # Numeric strings are compared with numeric values.
        try:
            number = float(stripped)
            if math.isfinite(number):
                return ("number", number)
        except ValueError:
            pass

        return ("text", stripped.casefold())

    return (type(value).__name__, value)

def get_path(doc, path):
    current = doc
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current

# Discovery uses only the first 200 records.
pairs = []

for old in db.students.find().sort("student_id", 1).limit(200):
    new = db.students_v3.find_one(
        {"student_id": old["student_id"]}
    )
    if new is None:
        raise RuntimeError("Missing V3 record.")
    pairs.append((flatten(old), flatten(new)))

old_fields = set().union(*(a.keys() for a, b in pairs))
new_fields = set().union(*(b.keys() for a, b in pairs))

removed = sorted(old_fields - new_fields)
added = sorted(new_fields - old_fields)

mapping = {}
discovery = {}
unresolved = {}

print("=" * 65)
print("SCHEMAGUARD AI - ENHANCED MAPPING ENGINE")
print("=" * 65)

for old_field in removed:
    candidates = []

    for new_field in added:
        available = 0
        matched = 0

        for old, new in pairs:
            if old_field in old and new_field in new:
                available += 1
                if normalize(old[old_field]) == normalize(new[new_field]):
                    matched += 1

        coverage = available / len(pairs)
        agreement = matched / available if available else 0

        # Requiring adequate coverage avoids selecting fields
        # that only match a small subset of the records.
        if coverage >= 0.65 and agreement >= 0.98:
            candidates.append({
                "path": new_field,
                "coverage": round(coverage, 4),
                "agreement": round(agreement, 4)
            })

    candidates.sort(
        key=lambda x: (x["coverage"], x["agreement"]),
        reverse=True
    )

    if len(candidates) == 1 or (
        len(candidates) > 1
        and candidates[0]["coverage"] - candidates[1]["coverage"] >= 0.20
    ):
        best = candidates[0]
        mapping[old_field] = best["path"]
        discovery[old_field] = best
    else:
        unresolved[old_field] = candidates

print("\nDISCOVERED FIELD MAPPINGS")

for old, new in mapping.items():
    metrics = discovery[old]
    print(f"\n{old} -> {new}")
    print(f"  Value agreement: {metrics['agreement']:.1%}")
    print(f"  Field coverage: {metrics['coverage']:.1%}")

print("\nUNRESOLVED FIELDS:", list(unresolved))

# Independently validate on student IDs 201 through 5000.
validation = {}

for old_field, new_field in mapping.items():
    total = 0
    available = 0
    normalized_matches = 0
    exact_matches = 0
    missing = 0

    for old in db.students.find(
        {"student_id": {"$gt": 200}},
        {"_id": 0}
    ):
        new = db.students_v3.find_one(
            {"student_id": old["student_id"]}
        )

        total += 1

        if new is None:
            missing += 1
            continue

        exists, value = get_path(new, new_field)

        if not exists:
            missing += 1
            continue

        available += 1

        original = old[old_field]

        if normalize(original) == normalize(value):
            normalized_matches += 1

        if type(original) is type(value) and original == value:
            exact_matches += 1

    validation[old_field] = {
        "mapped_to": new_field,
        "total": total,
        "available": available,
        "missing": missing,
        "normalized_matches": normalized_matches,
        "exact_matches": exact_matches,
        "normalized_agreement": (
            normalized_matches / total if total else 0
        ),
        "exact_agreement": (
            exact_matches / total if total else 0
        )
    }

print("\n" + "=" * 65)
print("HELD-OUT VALIDATION - 4800 RECORDS")
print("=" * 65)

for old_field, result in validation.items():
    print(f"\n{old_field} -> {result['mapped_to']}")
    print("  Available:", result["available"])
    print("  Missing:", result["missing"])
    print("  Normalized matches:", result["normalized_matches"])
    print("  Exact matches:", result["exact_matches"])
    print(
        "  Normalized agreement:",
        f"{result['normalized_agreement']:.2%}"
    )

report = {
    "method": "type_aware_normalized_value_mapping",
    "discovery_records": len(pairs),
    "validation_records": 4800,
    "mappings": mapping,
    "discovery": discovery,
    "unresolved": unresolved,
    "held_out_validation": validation
}

output = ROOT / "experiments/enhanced_mapping_results.json"

with open(output, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print("\n" + "=" * 65)
print("ENHANCED MAPPING EXPERIMENT COMPLETED")
print("Mappings discovered:", len(mapping))
print("Report saved:", output)
print("=" * 65)

client.close()
