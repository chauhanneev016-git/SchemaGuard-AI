
import os
import json
import random
from copy import deepcopy
from pathlib import Path

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

source = list(
    db.students.find({}, {"_id": 0}).sort("student_id", 1)
)

if len(source) != 5000:
    raise RuntimeError("Expected 5000 V1 student records.")

families = [
    "name_relocation",
    "cgpa_type_change",
    "phone_removal",
    "cgpa_corruption",
    "department_change",
    "mixed_type_and_missing"
]

rates = [0.10, 0.30, 0.60]

manifest = []
plans = []

for family_index, family in enumerate(families, start=1):
    for variant, rate in enumerate(rates, start=1):
        scenario_id = f"ML_F{family_index}_V{variant}"
        collection_name = f"ml_{family_index}_{variant}"

        plans.append({
            "id": scenario_id,
            "collection": collection_name,
            "family": family,
            "rate": rate
        })

existing = set(db.list_collection_names())
conflicts = [
    p["collection"] for p in plans
    if p["collection"] in existing
]

if conflicts:
    raise RuntimeError(
        "Scenario collections already exist: "
        + ", ".join(conflicts)
        + ". Nothing was overwritten."
    )

print("=" * 65)
print("SCHEMAGUARD AI - EXPANDED SCENARIO GENERATOR")
print("=" * 65)

for scenario in plans:
    rng = random.Random(
        1000 + families.index(scenario["family"]) * 10
        + rates.index(scenario["rate"])
    )

    chosen_ids = set(rng.sample(
        range(1, 5001),
        int(5000 * scenario["rate"])
    ))

    documents = []
    changed_count = 0

    for original in source:
        doc = deepcopy(original)
        sid = doc["student_id"]
        changed = sid in chosen_ids

        if changed:
            family = scenario["family"]

            if family == "name_relocation":
                doc["identity"] = {
                    "legal_name": doc.pop("name")
                }

            elif family == "cgpa_type_change":
                doc["cgpa"] = str(doc["cgpa"])

            elif family == "phone_removal":
                doc.pop("phone", None)

            elif family == "cgpa_corruption":
                cgpa = doc["cgpa"]
                doc["cgpa"] = round(
                    cgpa + 0.5 if cgpa <= 9.4
                    else cgpa - 0.5,
                    2
                )

            elif family == "department_change":
                alternatives = [
                    "CSE", "ECE", "AIML",
                    "Mechanical", "Civil", "Electrical"
                ]
                alternatives.remove(doc["department"])
                doc["department"] = rng.choice(alternatives)

            elif family == "mixed_type_and_missing":
                doc["cgpa"] = str(doc["cgpa"])
                doc.pop("phone", None)

            changed_count += 1

        doc["schema_version"] = scenario["id"]
        documents.append(doc)

    # Publish each scenario as a separate test collection.
    # Existing research collections are never modified.
    collection = db[scenario["collection"]]
    collection.insert_many(documents, ordered=False)
    collection.create_index("student_id", unique=True)

    manifest.append({
        **scenario,
        "total_documents": len(documents),
        "changed_documents": changed_count
    })

    print(
        f"{scenario['id']} | "
        f"{scenario['family']:<24} | "
        f"Changed: {changed_count}"
    )

output = ROOT / "experiments/expanded_scenario_manifest.json"

with open(output, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print("\n" + "=" * 65)
print("EXPANDED SCENARIOS CREATED")
print("Scenario collections:", len(manifest))
print("Total documents:", sum(
    x["total_documents"] for x in manifest
))
print("Manifest saved:", output)
print("=" * 65)

client.close()
