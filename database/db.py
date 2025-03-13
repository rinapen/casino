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
    """勝敗の連勝・連敗データを更新"""
    user_data = users_collection.find_one({"user_id": user_id})

    if not user_data:
        users_collection.insert_one({
            "user_id": user_id,
            "streaks": {game_type: {"win_streak": 0, "lose_streak": 0}}
        })
        user_data = users_collection.find_one({"user_id": user_id})

    # 既存の streak データを取得
    streak_data = user_data.get("streaks", {}).get(game_type, {"win_streak": 0, "lose_streak": 0})
    win_streak = streak_data.get("win_streak", 0)
    lose_streak = streak_data.get("lose_streak", 0)

    # 勝ちの場合：win_streak を増やし、lose_streak をリセット
    if is_win:
        win_streak += 1
        lose_streak = 0
    else:
        lose_streak += 1
        win_streak = 0

    # 更新クエリ
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {f"streaks.{game_type}.win_streak": win_streak, f"streaks.{game_type}.lose_streak": lose_streak}},
        upsert=True
    )
def get_user_streaks(user_id, game_type):
    """ゲームタイプごとのユーザーの連勝・連敗記録を取得"""
    user = users_collection.find_one({"user_id": user_id}, {"streaks": 1})  # `streaks` フィールドのみ取得
    
    if not user or "streaks" not in user:
        return 0, 0  # データがない場合は (0, 0) を返す

    # ゲームタイプごとの streak を取得
    game_streaks = user.get("streaks", {}).get(game_type, {})

    return game_streaks.get("win_streak", 0), game_streaks.get("lose_streak", 0)

def update_bet_history(user_id, game_type, amount, is_win):
    """ユーザーのベット履歴をデータベースに記録"""

    bet_entry = {
        "amount": amount,
        "is_win": bool(is_win),  # ✅ `bool` に変換
        "timestamp": datetime.datetime.now()
    }

    bet_history_collection.update_one(
        {"user_id": user_id},
        {"$push": {f"bet_history.{game_type}.bets": bet_entry}},
        upsert=True
    )


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