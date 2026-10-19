
import os
import json
import hashlib
from pathlib import Path
from collections import Counter, defaultdict

from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DATABASE_NAME", "schemaguard_research")

if DB_NAME != "schemaguard_research":
    raise RuntimeError("Unexpected database.")

with open(ROOT / "experiments/workload_100_v1.json",
          encoding="utf-8") as f:
    workload = json.load(f)

with open(ROOT / "experiments/expanded_scenario_manifest.json",
          encoding="utf-8") as f:
    scenarios = json.load(f)

client = MongoClient(URI, serverSelectionTimeoutMS=5000)
client.admin.command("ping")
db = client[DB_NAME]

def fingerprint(rows):
    data = json.dumps(rows, sort_keys=True, default=str)
    return hashlib.sha256(data.encode()).hexdigest()

def original_query(collection, test):
    projection = {field: 1 for field in test["fields"]}
    projection["_id"] = 0

    return list(
        collection.find(test["filter"], projection)
        .sort(test["sort"], 1)
    )

def adapted_query(collection, test, is_student):
    if not is_student:
        return original_query(collection, test)

    # Canonicalize supported mixed-version fields.
    # This is an evaluation adapter, NOT the ML predictor.
    pipeline = [
        {
            "$addFields": {
                "name": {
                    "$ifNull": [
                        "$name",
                        "$identity.legal_name"
                    ]
                },
                "cgpa": {
                    "$convert": {
                        "input": "$cgpa",
                        "to": "double",
                        "onError": None,
                        "onNull": None
                    }
                }
            }
        },
        {"$match": test["filter"]},
        {"$sort": {test["sort"]: 1}},
        {
            "$project": {
                **{field: 1 for field in test["fields"]},
                "_id": 0
            }
        }
    ]

    return list(collection.aggregate(pipeline))

print("=" * 66)
print("SCHEMAGUARD AI - EXPANDED COMPATIBILITY BENCHMARK")
print("=" * 66)

results = []
errors = []

for number, scenario in enumerate(scenarios, start=1):
    scenario_id = scenario["id"]
    family = scenario["family"]
    collection = db[scenario["collection"]]

    if collection.count_documents({}) != 5000:
        raise RuntimeError(f"Incomplete scenario: {scenario_id}")

    scenario_results = []

    for test in workload["queries"]:
        is_student = test["collection"] == "students"

        target = (
            collection
            if is_student
            else db[test["collection"]]
        )

        expected_hash = test["expected_fingerprint"]

        try:
            raw = original_query(target, test)
            adapted = adapted_query(target, test, is_student)

            raw_match = (
                fingerprint(raw) == expected_hash
                and len(raw) == test["expected_count"]
            )

            adapted_match = (
                fingerprint(adapted) == expected_hash
                and len(adapted) == test["expected_count"]
            )

            if raw_match:
                status = "EXACT_MATCH"
            elif adapted_match:
                status = "ADAPTER_RESTORED"
            else:
                status = "REVIEW_REQUIRED"

            result = {
                "scenario": scenario_id,
                "family": family,
                "rate": scenario["rate"],
                "query_id": test["id"],
                "category": test["category"],
                "expected_count": test["expected_count"],
                "raw_count": len(raw),
                "adapted_count": len(adapted),
                "raw_match": raw_match,
                "adapted_match": adapted_match,
                "status": status,
                "requires_review": int(
                    status == "REVIEW_REQUIRED"
                )
            }

        except Exception as exc:
            result = {
                "scenario": scenario_id,
                "family": family,
                "rate": scenario["rate"],
                "query_id": test["id"],
                "category": test["category"],
                "status": "EXECUTION_ERROR",
                "requires_review": 1,
                "error": str(exc)
            }
            errors.append(result)

        scenario_results.append(result)
        results.append(result)

    counts = Counter(r["status"] for r in scenario_results)

    print(
        f"[{number:02d}/18] {scenario_id:<10} "
        f"Exact: {counts['EXACT_MATCH']:3d} | "
        f"Restored: {counts['ADAPTER_RESTORED']:3d} | "
        f"Review: {counts['REVIEW_REQUIRED']:3d} | "
        f"Errors: {counts['EXECUTION_ERROR']:2d}"
    )

summary = Counter(r["status"] for r in results)

by_family = {}

for family in sorted(set(r["family"] for r in results)):
    subset = [r for r in results if r["family"] == family]
    by_family[family] = dict(Counter(
        r["status"] for r in subset
    ))

report = {
    "experiment": "expanded_migration_compatibility",
    "evaluation_count": len(results),
    "scenario_count": len(scenarios),
    "query_count": len(workload["queries"]),
    "method": "original_query_vs_canonical_adapter",
    "label_policy": {
        "EXACT_MATCH": "Original query output unchanged",
        "ADAPTER_RESTORED": (
            "Controlled adapter restores original output"
        ),
        "REVIEW_REQUIRED": (
            "Output differs even after supported adaptation"
        ),
        "EXECUTION_ERROR": "Query execution failed"
    },
    "summary": dict(summary),
    "by_family": by_family,
    "results": results
}

output = ROOT / "experiments/expanded_benchmark_1800.json"

with open(output, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print("\n" + "=" * 66)
print("EXPANDED BENCHMARK COMPLETED")
print("=" * 66)
print("Total evaluations:", len(results))
print("Exact matches:", summary["EXACT_MATCH"])
print("Adapter restored:", summary["ADAPTER_RESTORED"])
print("Review required:", summary["REVIEW_REQUIRED"])
print("Execution errors:", summary["EXECUTION_ERROR"])
print("Report saved:", output)

client.close()
