
import os
import random
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DATABASE_NAME", "schemaguard_research")

if DB_NAME != "schemaguard_research":
    raise RuntimeError("Unexpected database. Operation cancelled.")

random.seed(42)

client = MongoClient(URI, serverSelectionTimeoutMS=5000)
client.admin.command("ping")
db = client[DB_NAME]

if "students_v3" in db.list_collection_names():
    raise RuntimeError(
        "students_v3 already exists. Existing data preserved."
    )

if db.students.count_documents({}) != 5000:
    raise RuntimeError("Expected 5000 V1 student documents.")

print("=" * 60)
print("SCHEMAGUARD AI - CHALLENGING SCHEMA V3")
print("=" * 60)

documents = []
scenario_counts = {
    "field_movement": 0,
    "type_change": 0,
    "missing_phone": 0,
    "name_formatting": 0,
    "ambiguous_department": 0
}

for old in db.students.find().sort("student_id", 1):
    sid = old["student_id"]

    # S1: All records use nested field paths.
    new = {
        "student_id": sid,
        "profile": {
            "full_name": old["name"]
        },
        "academics": {
            "branch": old["department"],
            "cgpa": old["cgpa"]
        },
        "contact": {
            "mobile": old["phone"]
        },
        "email": old["email"],
        "semester": old["semester"],
        "admission_year": old["admission_year"],
        "status": old["status"],
        "address": old["address"],
        "schema_version": 3
    }
    scenario_counts["field_movement"] += 1

    # S2: CGPA converted from float to string.
    if sid % 5 == 0:
        new["academics"]["cgpa"] = str(old["cgpa"])
        scenario_counts["type_change"] += 1

    # S3: Phone field removed.
    if sid % 10 == 1:
        new["contact"].pop("mobile")
        scenario_counts["missing_phone"] += 1

    # S4: Names normalized to uppercase.
    if sid % 7 == 0:
        new["profile"]["full_name"] = old["name"].upper()
        scenario_counts["name_formatting"] += 1

    # S5: Add an alternate, often identical department.
    if sid % 4 == 0:
        new["academics"]["registered_branch"] = old["department"]
        scenario_counts["ambiguous_department"] += 1

    documents.append(new)

assert len(documents) == 5000

# Create only the new V3 collection.
db.students_v3.insert_many(documents)
db.students_v3.create_index("student_id", unique=True)

print("\nV3 DATASET CREATED SUCCESSFULLY")
print("Documents:", db.students_v3.count_documents({}))

print("\nSCENARIO DISTRIBUTION")
for scenario, count in scenario_counts.items():
    print(f"{scenario}: {count}")

print("\nOriginal V1 and V2 collections: PRESERVED")
print("=" * 60)

client.close()
