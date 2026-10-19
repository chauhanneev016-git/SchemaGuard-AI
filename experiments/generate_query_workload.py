
import os
import json
import random
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

random.seed(42)

client = MongoClient(uri, serverSelectionTimeoutMS=5000)
client.admin.command("ping")
db = client[db_name]

if db.students.count_documents({}) != 5000:
    raise RuntimeError("Expected 5000 V1 students.")

queries = []

def add_query(category, collection, filter_obj, fields, sort):
    queries.append({
        "id": f"W{len(queries)+1:03d}",
        "category": category,
        "collection": collection,
        "filter": filter_obj,
        "fields": fields,
        "sort": sort
    })

branches = [
    "CSE", "ECE", "AIML",
    "Mechanical", "Civil", "Electrical"
]

# Group A: Department and semester queries
for i in range(20):
    add_query(
        "department",
        "students",
        {
            "department": branches[i % len(branches)],
            "semester": (i % 8) + 1
        },
        ["student_id", "name", "department"],
        "student_id"
    )

# Group B: CGPA filtering
for i in range(20):
    threshold = round(6.0 + i * 0.15, 2)

    add_query(
        "cgpa",
        "students",
        {"cgpa": {"$gte": threshold}},
        ["student_id", "name", "cgpa"],
        "student_id"
    )

# Group C: Name searches
for letter in "ABCDEFGHIJKLMNOPQRST":
    add_query(
        "name",
        "students",
        {"name": {"$regex": f"^{letter}", "$options": "i"}},
        ["student_id", "name"],
        "student_id"
    )

# Group D: Contact lookups
# Includes IDs that lose their phone number in V3.
for student_id in range(101, 121):
    add_query(
        "contact",
        "students",
        {"student_id": student_id},
        ["student_id", "name", "phone"],
        "student_id"
    )

# Group E: Scholarship filtering
types = ["Merit", "Need-Based", "Sports", "Research"]

for i in range(20):
    add_query(
        "scholarship",
        "scholarships",
        {
            "scholarship_type": types[i % 4],
            "approved": bool(i % 2)
        },
        ["scholarship_id", "student_id", "amount"],
        "scholarship_id"
    )

def fingerprint(data):
    serialized = json.dumps(
        data, sort_keys=True, default=str
    )
    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()

print("=" * 60)
print("SCHEMAGUARD AI - QUERY WORKLOAD GENERATION")
print("=" * 60)

results = []

for query in queries:
    projection = {field: 1 for field in query["fields"]}
    projection["_id"] = 0

    rows = list(
        db[query["collection"]]
        .find(query["filter"], projection)
        .sort(query["sort"], 1)
    )

    results.append({
        **query,
        "expected_count": len(rows),
        "expected_fingerprint": fingerprint(rows),
        "expected_results": rows
    })

    print(
        f"{query['id']} | "
        f"{query['category']:<12} | "
        f"Results: {len(rows)}"
    )

report = {
    "database": db_name,
    "schema_version": 1,
    "workload_size": len(results),
    "queries": results
}

output = ROOT / "experiments" / "workload_100_v1.json"

with open(output, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, default=str)

print("\n" + "=" * 60)
print("WORKLOAD GENERATION COMPLETE")
print("Total queries:", len(results))
print("Categories:", 5)
print("Baseline saved:", output)
print("=" * 60)

client.close()
