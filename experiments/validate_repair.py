
import os
import json
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
db_name = os.getenv("DATABASE_NAME", "schemaguard_research")

if db_name != "schemaguard_research":
    raise RuntimeError("Unexpected database.")

with open(ROOT / "experiments/repair_results.json", encoding="utf-8") as f:
    repair = json.load(f)

mapping = repair["field_mappings"]
sample_size = repair["sample_size"]

client = MongoClient(uri, serverSelectionTimeoutMS=5000)
client.admin.command("ping")
db = client[db_name]

def get_field(document, path):
    current = document
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return False, None
        current = current[key]
    return True, current

print("=" * 60)
print("SCHEMAGUARD AI - HELD-OUT VALIDATION")
print("=" * 60)

records = db.students.find(
    {}, {"_id": 0}
).sort("student_id", 1).skip(sample_size)

total_records = 0
correct_records = 0
field_matches = {field: 0 for field in mapping}
field_errors = {field: 0 for field in mapping}
missing_records = 0

for old in records:
    total_records += 1

    new = db.students_v2.find_one(
        {"student_id": old["student_id"]}
    )

    if new is None:
        missing_records += 1
        continue

    record_correct = True

    for old_field, new_field in mapping.items():
        old_exists, old_value = get_field(old, old_field)
        new_exists, new_value = get_field(new, new_field)

        matched = (
            old_exists
            and new_exists
            and type(old_value) is type(new_value)
            and old_value == new_value
        )

        if matched:
            field_matches[old_field] += 1
        else:
            field_errors[old_field] += 1
            record_correct = False

    if record_correct:
        correct_records += 1

print("\nVALIDATION RESULTS")
print("Discovery sample:", sample_size)
print("Held-out records:", total_records)
print("Missing V2 records:", missing_records)

for field, new_field in mapping.items():
    accuracy = (
        field_matches[field] / total_records * 100
        if total_records else 0
    )
    print(f"\n{field} -> {new_field}")
    print(f"  Matches: {field_matches[field]}/{total_records}")
    print(f"  Agreement: {accuracy:.2f}%")
    print(f"  Mismatches: {field_errors[field]}")

record_accuracy = (
    correct_records / total_records * 100
    if total_records else 0
)

print("\n" + "=" * 60)
print("OVERALL VALIDATION")
print("Fully matching records:", correct_records)
print("Record agreement:", f"{record_accuracy:.2f}%")
print("=" * 60)

report = {
    "discovery_sample": sample_size,
    "held_out_records": total_records,
    "correct_records": correct_records,
    "missing_records": missing_records,
    "record_agreement_percent": record_accuracy,
    "field_matches": field_matches,
    "field_errors": field_errors
}

output = ROOT / "experiments/validation_results.json"
with open(output, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print("Report saved:", output)

client.close()
