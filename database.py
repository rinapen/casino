import pymongo
import datetime
from config import MONGO_URI, DB_NAME, TOKENS_COLLECTION, USERS_COLLECTION, TRANSACTIONS_COLLECTION
import pytz 

client = pymongo.MongoClient(MONGO_URI)
db = client[DB_NAME]
tokens_collection = db[TOKENS_COLLECTION]
users_collection = db[USERS_COLLECTION]
transactions_collection = db[TRANSACTIONS_COLLECTION]

def get_tokens():
    return tokens_collection.find_one({}) or {}

def save_tokens(access_token, refresh_token, device_uuid):
    tokens_collection.update_one({}, {"$set": {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "device_uuid": device_uuid
    }}, upsert=True)

def get_user_balance(user_id):
    user = users_collection.find_one({"user_id": user_id})
    return user["balance"] if user else None

def update_user_balance(user_id, amount):
    users_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"balance": int(amount)}},  # **intに変換して保存**
        upsert=True
    )

def register_user(user_id, email, password, sender_external_id):
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {
            "email": email,
            "password": password,
            "sender_external_id": sender_external_id,
            "balance": 0
        }},
        upsert=True
    )

def log_transaction(user_id, type, amount, fee, total, receiver=None):
    DIFF_JST_FROM_UTC = 9
    now = datetime.datetime.now()

    transaction = {
        "user_id": user_id,
        "type": type,  # "in", "out", "transfer"
        "amount": amount,
        "fee": fee,
        "total": total,
        "receiver": receiver,
        "timestamp": now  # **JST（日本標準時）で記録**
    }

    transactions_collection.insert_one(transaction)