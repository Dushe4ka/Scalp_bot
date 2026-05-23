from pymongo import MongoClient
from config import MONGO_URI, MONGO_DB

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]

subscribers = db["subscribers"]

def add_subscriber(user_id: int, username: str):
    subscribers.update_one(
        {"user_id": user_id},
        {"$set": {"username": username}},
        upsert=True
    )

def remove_subscriber(user_id: int):
    subscribers.delete_one({"user_id": user_id})

def is_subscriber(user_id: int) -> bool:
    return subscribers.find_one({"user_id": user_id}) is not None

def get_subscribers() -> list[int]:
    return [subscriber["user_id"] for subscriber in subscribers.find()]