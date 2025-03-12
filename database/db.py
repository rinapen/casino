import pymongo
import config
import datetime

client = pymongo.MongoClient(config.MONGO_URI)
db = client[config.DB_NAME]

tokens_collection = db[config.TOKENS_COLLECTION]

user_transactions_collection = db[config.USER_TRANSACTIONS_COLLECTION]
casino_transactions_collection = db[config.CASINO_TRANSACTION_COLLECTION]
users_collection = db[config.USERS_COLLECTION]
casino_stats_collection = db[config.CASINO_STATS_COLLECTION]
models_collection = db[config.MODELS_COLLECTION]
bet_history_collection = db[config.BET_HISTORY_COLLECTION]

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
    """ユーザーのPNC残高を更新（増減）"""
    users_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"balance": amount}},
        upsert=True
    )

def update_user_streak(user_id, game_type, is_win):
    """ユーザーの連勝・連敗記録を更新"""
    if is_win:
        users_collection.update_one(
            {"user_id": user_id},
            {
                "$inc": {"win_streak": 1, "lose_streak": -1},
                "$max": {"win_streak": 0}  # 負の数にならないようにする
            },
            upsert=True
        )
    else:
        users_collection.update_one(
            {"user_id": user_id},
            {
                "$inc": {"win_streak": -1, "lose_streak": 1},
                "$max": {"lose_streak": 0}  # 負の数にならないようにする
            },
            upsert=True
        )

def get_user_streaks(user_id, game_type):
    """ユーザーの連勝・連敗記録を取得"""
    user = users_collection.find_one({"user_id": user_id}, {"win_streak": 1, "lose_streak": 1})
    return user.get("win_streak", 0), user.get("lose_streak", 0)

def register_user(user_id, username, sender_external_id):
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {
            "username": username,
            "sender_external_id": sender_external_id,
            "balance": 0
        }},
        upsert=True
    )

def log_transaction(user_id, type, amount, fee, total, receiver=None):
    """ ユーザーの取引履歴を `transactions` にリスト形式で記録 (JST対応) """
    now = datetime.datetime.now()
    transaction = {
        "type": type,  # "in", "out", "send"
        "amount": amount,
        "fee": fee,
        "total": total,
        "receiver": receiver,
        "timestamp": now  # **JST（日本標準時）**
    }

    user_transactions_collection.update_one(
        {"user_id": user_id},
        {"$push": {"transactions": transaction}}, 
        upsert=True
    )