
import os
import sys
import json
import hashlib
from pathlib import Path

from pymongo import MongoClient
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DATABASE_NAME", "schemaguard_research")

if DB_NAME != "schemaguard_research":
    sys.exit("Unexpected database name. Test stopped.")

client = MongoClient(URI, serverSelectionTimeoutMS=5000)
client.admin.command("ping")
db = client[DB_NAME]

if db.students.count_documents({"schema_version": 1}) != 5000:
    sys.exit("Expected 5000 V1 student records. Test stopped.")

# Original V1 application queries
queries = [
    {
        "id": "Q1",
        "name": "Search students by department",
        "collection": "students",
        "filter": {"department": "ECE"},
        "fields": ["student_id", "name", "department"],
        "sort": "student_id"
    },
    {
        "id": "Q2",
        "name": "Find students with high CGPA",
        "collection": "students",
        "filter": {"cgpa": {"$gte": 8.5}},
        "fields": ["student_id", "name", "cgpa"],
        "sort": "student_id"
    },
    {
        "id": "Q3",
        "name": "Search student by name",
        "collection": "students",
        "filter": {"name": {"$regex": "^A", "$options": "i"}},
        "fields": ["student_id", "name"],
        "sort": "student_id"
    },
    {
        "id": "Q4",
        "name": "Find student contact details",
        "collection": "students",
        "filter": {"student_id": 101},
        "fields": ["student_id", "name", "phone"],
        "sort": "student_id"
    },
    {
        "id": "Q5",
        "name": "Find approved scholarships",
        "collection": "scholarships",
        "filter": {"approved": True},
        "fields": ["scholarship_id", "student_id", "amount"],
        "sort": "scholarship_id"
    }
]

report = {
    "database": DB_NAME,
    "schema_version": 1,
    "tests": []
}

print("\n" + "=" * 55)
print("SCHEMAGUARD AI - BASELINE QUERY TESTING")
print("=" * 55)

for query in queries:
    projection = {field: 1 for field in query["fields"]}
    projection["_id"] = 0

    results = list(
        db[query["collection"]]
        .find(query["filter"], projection)
        .sort(query["sort"], 1)
    )

    normalized = json.dumps(
        results, sort_keys=True, default=str
    )

    fingerprint = hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()

    report["tests"].append({
        **query,
        "result_count": len(results),
        "result_fingerprint": fingerprint,
        "expected_results": results
    })

    print(f"\n{query['id']}: {query['name']}")
    print(f"  Documents returned: {len(results)}")
    print(f"  Status: {'PASS' if results else 'EMPTY'}")
    print(f"  Fingerprint: {fingerprint[:16]}...")

output = ROOT / "experiments" / "baseline_v1.json"
output.parent.mkdir(parents=True, exist_ok=True)

with open(output, "w", encoding="utf-8") as file:
    json.dump(report, file, indent=2, default=str)

print("\n" + "=" * 55)
print("BASELINE TESTING COMPLETED")
print("Queries tested:", len(queries))
print("Results saved:", output)
print("=" * 55)

client.close()
