import pymongo
from pymongo.database import Database
from pymongo.collection import Collection

from config import MONGO_URI, MONGO_DB_NAME


_client: pymongo.MongoClient | None = None
_db: Database | None = None


def get_db() -> Database:
    global _client, _db
    if _db:
        return _db

    _client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    _db = _client[MONGO_DB_NAME]
    # Trigger a ping to fail fast if connection is bad
    _db.command("ping")
    return _db


def users_collection() -> Collection:
    return get_db()["users"]


def designs_collection() -> Collection:
    return get_db()["designs"]
