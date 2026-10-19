
import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DATABASE_NAME", "schemaguard_research")

if DB_NAME != "schemaguard_research":
    raise ValueError("Unexpected database. Migration cancelled.")

client = MongoClient(URI, serverSelectionTimeoutMS=5000)
client.admin.command("ping")

db = client[DB_NAME]
source = db["students"]

if source.count_documents({}) != 5000:
    raise ValueError("V1 collection must contain 5000 documents.")

if source.count_documents({"schema_version": {"$ne": 1}}):
    raise ValueError("Source contains non-V1 documents.")

print("=" * 55)
print("SCHEMAGUARD AI - SCHEMA EVOLUTION V1 TO V2")
print("=" * 55)

# Build the new collection using a temporary staging collection.
staging_name = "students_v2_staging"
staging = db[staging_name]
staging.drop()

batch = []
total = 0

for student in source.find():
    transformed = {
        "student_id": student["student_id"],
        "profile": {
            "full_name": student["name"]
        },
        "contact": {
            "mobile": student["phone"]
        },
        "academics": {
            "branch": student["department"],
            "cgpa": student["cgpa"]
        },
        "email": student["email"],
        "semester": student["semester"],
        "admission_year": student["admission_year"],
        "status": student["status"],
        "address": student["address"],
        "schema_version": 2
    }

    batch.append(transformed)

    if len(batch) >= 500:
        staging.insert_many(batch)
        total += len(batch)
        batch.clear()

if batch:
    staging.insert_many(batch)
    total += len(batch)

staging.create_index(
    [("student_id", ASCENDING)],
    unique=True
)

print("Documents transformed:", total)

# Verify all important data before accepting the migration.
errors = []

for old in source.find():
    new = staging.find_one({"student_id": old["student_id"]})

    if new is None:
        errors.append(f"Missing student {old['student_id']}")
        continue

    checks = [
        new["profile"]["full_name"] == old["name"],
        new["contact"]["mobile"] == old["phone"],
        new["academics"]["branch"] == old["department"],
        new["academics"]["cgpa"] == old["cgpa"],
        new["email"] == old["email"],
        new["semester"] == old["semester"],
        new["admission_year"] == old["admission_year"],
        new["status"] == old["status"],
        new["address"] == old["address"],
        new["schema_version"] == 2
    ]

    if not all(checks):
        errors.append(f"Mismatch for student {old['student_id']}")

if total != 5000 or errors:
    print("Migration validation FAILED")
    print("First errors:", errors[:10])
    client.close()
    raise RuntimeError("V2 migration validation failed.")

# Publish only when validation succeeds.
# Never overwrite an existing students_v2 collection.
if "students_v2" in db.list_collection_names():
    client.close()
    raise RuntimeError(
        "students_v2 already exists. Existing data was preserved."
    )

staging.rename("students_v2", dropTarget=False)

print("\n" + "=" * 55)
print("MIGRATION COMPLETED SUCCESSFULLY")
print("Source collection: students")
print("New collection: students_v2")
print("Documents migrated:", total)
print("Data validation errors:", len(errors))
print("Original V1 collection: PRESERVED")
print("Schema version: V2")
print("=" * 55)

client.close()

