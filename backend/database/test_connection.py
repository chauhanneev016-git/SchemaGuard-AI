
import os
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")

try:
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")

    print("================================")
    print("SCHEMAGUARD AI")
    print("================================")
    print("MongoDB Connection: SUCCESS")
    print("Database:", os.getenv("DATABASE_NAME"))
    print("MongoDB Version:", client.server_info()["version"])

    client.close()

except Exception as e:
    print("MongoDB Connection: FAILED")
    print("Error:", e)
