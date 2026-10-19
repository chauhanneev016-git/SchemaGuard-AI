
import os
import json
from pathlib import Path
from copy import deepcopy

from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DATABASE_NAME", "schemaguard_research")

if DB_NAME != "schemaguard_research":
    raise RuntimeError("Unexpected database name.")

client = MongoClient(URI, serverSelectionTimeoutMS=5000)
client.admin.command("ping")
db = client[DB_NAME]

if db.students.count_documents({}) != 5000:
    raise RuntimeError("Expected 5000 original student records.")

scenarios = {
    "S4": {
        "collection": "students_s4",
        "description": "Name field relocation",
        "change": "name to identity.legal_name"
    },
    "S5": {
        "collection": "students_s5",
        "description": "CGPA type transformation",
        "change": "float CGPA to string"
    },
    "S6": {
        "collection": "students_s6",
        "description": "Missing contact data",
        "change": "remove phones for selected students"
    },
    "S7": {
        "collection": "students_s7",
        "description": "CGPA value corruption",
        "change": "modify selected numerical CGPA values"
    }
}

# Never overwrite collections from earlier experiments.
existing = set(db.list_collection_names())

for scenario in scenarios.values():
    if scenario["collection"] in existing:
        raise RuntimeError(
            f"{scenario['collection']} already exists. "
            "No existing collection was overwritten."
        )

print("=" * 60)
print("SCHEMAGUARD AI - ML SCENARIO GENERATION")
print("=" * 60)

originals = list(
    db.students.find({}, {"_id": 0}).sort("student_id", 1)
)

for scenario_id, info in scenarios.items():
    documents = []
    affected = 0

    for source in originals:
        doc = deepcopy(source)
        sid = doc["student_id"]
        changed = False

        if scenario_id == "S4":
            doc["identity"] = {
                "legal_name": doc.pop("name")
            }
            changed = True

        elif scenario_id == "S5":
            doc["cgpa"] = str(doc["cgpa"])
            changed = True

        elif scenario_id == "S6":
            if sid % 5 == 0:
                doc.pop("phone", None)
                changed = True

        elif scenario_id == "S7":
            if sid % 10 == 0:
                original = doc["cgpa"]
                doc["cgpa"] = round(
                    original + 0.5
                    if original <= 9.4
                    else original - 0.5,
                    2
                )
                changed = True

        doc["schema_version"] = scenario_id
        documents.append(doc)

        if changed:
            affected += 1

    collection = db[info["collection"]]
    collection.insert_many(documents)
    collection.create_index("student_id", unique=True)

    info["documents"] = len(documents)
    info["affected_documents"] = affected

    print(f"\n{scenario_id}: {info['description']}")
    print("Collection:", info["collection"])
    print("Documents:", len(documents))
    print("Changed documents:", affected)

output = ROOT / "experiments/scenario_manifest.json"

with open(output, "w", encoding="utf-8") as f:
    json.dump(scenarios, f, indent=2)

print("\n" + "=" * 60)
print("SCENARIO GENERATION COMPLETED")
print("New collections:", len(scenarios))
print("Total new documents:", sum(
    s["documents"] for s in scenarios.values()
))
print("Manifest:", output)
print("=" * 60)

client.close()
