
import os
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from faker import Faker
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DATABASE_NAME", "schemaguard_research")

if DB_NAME != "schemaguard_research":
    raise ValueError("Refusing to seed an unexpected database.")

random.seed(42)
fake = Faker("en_IN")
Faker.seed(42)

client = MongoClient(URI, serverSelectionTimeoutMS=5000)
client.admin.command("ping")
db = client[DB_NAME]

# Only reset the four collections belonging to this demo dataset.
collections = ["students", "courses", "enrollments", "scholarships"]
for name in collections:
    db[name].drop()

branches = ["CSE", "ECE", "AIML", "Mechanical", "Civil", "Electrical"]
semesters = list(range(1, 9))
statuses = ["Active", "Active", "Active", "Graduated", "On Leave"]

print("Creating SchemaGuard Research Dataset V1...")

# 1. STUDENTS
students = []

for i in range(1, 5001):
    students.append({
        "student_id": i,
        "name": fake.name(),
        "email": f"student{i}@university.edu",
        "phone": fake.numerify("##########"),
        "department": random.choice(branches),
        "semester": random.choice(semesters),
        "cgpa": round(random.uniform(5.0, 9.9), 2),
        "admission_year": random.randint(2022, 2026),
        "status": random.choice(statuses),
        "address": {
            "city": fake.city(),
            "state": fake.state()
        },
        "schema_version": 1
    })

db.students.insert_many(students, ordered=False)
print("Students created:", db.students.count_documents({}))

# 2. COURSES
courses = []

for i in range(1, 41):
    courses.append({
        "course_id": f"CRS{i:03d}",
        "course_name": f"University Course {i}",
        "department": random.choice(branches),
        "credits": random.choice([2, 3, 4]),
        "schema_version": 1
    })

db.courses.insert_many(courses)
print("Courses created:", db.courses.count_documents({}))

# 3. ENROLLMENTS
enrollments = []

for i in range(1, 12001):
    enrollments.append({
        "enrollment_id": i,
        "student_id": random.randint(1, 5000),
        "course_id": f"CRS{random.randint(1, 40):03d}",
        "grade": random.choice(["O", "A+", "A", "B+", "B", "C"]),
        "enrolled_on": datetime.now(timezone.utc)
            - timedelta(days=random.randint(0, 730)),
        "schema_version": 1
    })

db.enrollments.insert_many(enrollments, ordered=False)
print("Enrollments created:", db.enrollments.count_documents({}))

# 4. SCHOLARSHIPS
scholarships = []

selected_ids = random.sample(range(1, 5001), 1000)

for i, student_id in enumerate(selected_ids, start=1):
    scholarships.append({
        "scholarship_id": i,
        "student_id": student_id,
        "scholarship_type": random.choice([
            "Merit", "Need-Based", "Sports", "Research"
        ]),
        "amount": random.choice([10000, 15000, 25000, 40000]),
        "approved": random.choice([True, False]),
        "schema_version": 1
    })

db.scholarships.insert_many(scholarships)
print("Scholarships created:", db.scholarships.count_documents({}))

# Application-level identifiers must be unique.
db.students.create_index("student_id", unique=True)
db.students.create_index("email", unique=True)
db.courses.create_index("course_id", unique=True)
db.enrollments.create_index("enrollment_id", unique=True)
db.scholarships.create_index("scholarship_id", unique=True)

print("\n" + "=" * 50)
print("SCHEMAGUARD AI - DATASET V1 READY")
print("=" * 50)

total = sum(db[name].count_documents({}) for name in collections)
print("Database:", db.name)
print("Total documents:", total)
print("Schema version: V1")
print("Collections:", db.list_collection_names())
print("=" * 50)

client.close()
