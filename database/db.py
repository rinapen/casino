"""
データベース接続とコレクション管理モジュール
MongoDBとの接続を一元管理し、型安全なデータベース操作を提供します
"""
import datetime
from datetime import timedelta
from typing import Optional, Any

import pymongo
from pymongo.collection import Collection
from pymongo.database import Database

import config

# ========================================
# データベース接続（シングルトン）
# ========================================
_client: Optional[pymongo.MongoClient] = None
_db: Optional[Database] = None


def get_client() -> pymongo.MongoClient:
    """MongoDBクライアントのシングルトンインスタンスを取得"""
    global _client
    if _client is None:
        _client = pymongo.MongoClient(config.MONGO_URI)
    return _client


def get_database() -> Database:
    """データベースインスタンスを取得"""
    global _db
    if _db is None:
        _db = get_client()[config.DB_NAME]
    return _db


# ========================================
# コレクション定義
# ========================================
def get_collection(collection_name: str) -> Collection:
    """指定されたコレクションを取得"""
    return get_database()[collection_name]


# メインコレクション
tokens_collection = get_collection(config.TOKENS_COLLECTION)
blacklist_collection = get_collection(config.BLACKLIST_COLLECTION)
user_transactions_collection = get_collection(config.USER_TRANSACTIONS_COLLECTION)
casino_transactions_collection = get_collection(config.CASINO_TRANSACTION_COLLECTION)
users_collection = get_collection(config.USERS_COLLECTION)
casino_stats_collection = get_collection(config.CASINO_STATS_COLLECTION)
models_collection = get_collection(config.MODELS_COLLECTION)
bet_history_collection = get_collection(config.BET_HISTORY_COLLECTION)
bot_state_collection = get_collection(config.BOT_STATE_COLLECTION)

# 追加コレクション
payin_settings_collection = get_collection("payin_settings")
invited_users_collection = get_collection("invited_users")
invites_collection = get_collection("invites")
invite_redeem_collection = get_collection("invite_redeem")
active_users_collection = get_collection("active_users")
pf_collection = get_collection("pf_params")
casino_tables_collection = get_collection("casino_tables")

# ========================================
# Provably Fair関連
# ========================================
def load_pf_params(user_id: int) -> tuple[Optional[str], int]:
    """ユーザーのProvably Fairパラメータを読み込む"""
    doc = pf_collection.find_one({"user_id": user_id})
    if doc:
        return doc.get("client_seed"), doc.get("nonce", 0)
    return None, 0


def save_pf_params(user_id: int, client_seed: str, server_seed: str, nonce: int) -> None:
    """ユーザーのProvably Fairパラメータを保存"""
    pf_collection.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "client_seed": client_seed,
                "server_seed": server_seed,
                "nonce": nonce
            }
        },
        upsert=True
    )


# ========================================
# ブラックリスト管理
# ========================================
def is_blacklisted(user_id: int) -> bool:
    """ユーザーがブラックリストに登録されているか確認"""
    return blacklist_collection.find_one({"user_id": user_id}) is not None


# ========================================
# トークン管理
# ========================================
def get_tokens() -> dict[str, Any]:
    """PayPayトークンを取得"""
    return tokens_collection.find_one({}) or {}


def save_tokens(access_token: str, refresh_token: str, device_uuid: str) -> None:
    """PayPayトークンを保存"""
    tokens_collection.update_one(
        {},
        {
            "$set": {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "device_uuid": device_uuid
            }
        },
        upsert=True
    )


# ========================================
# ユーザー残高管理
# ========================================
def get_user_balance(user_id: int) -> Optional[int]:
    """ユーザーのPNC残高を取得"""
    user = users_collection.find_one({"user_id": user_id})
    return user["balance"] if user else None


def update_user_balance(user_id: int, amount: int) -> None:
    """ユーザーのPNC残高を更新（増減）"""
    users_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"balance": amount}},
        upsert=True
    )

# ========================================
# ユーザーストリーク管理
# ========================================
def update_user_streak(user_id: int, game_type: str, is_win: bool) -> None:
    """勝敗の連勝・連敗データを更新"""
    user_data = users_collection.find_one({"user_id": user_id})

    if not user_data:
        users_collection.insert_one({
            "user_id": user_id,
            "streaks": {game_type: {"win_streak": 0, "lose_streak": 0}}
        })
        user_data = users_collection.find_one({"user_id": user_id})

    streak_data = user_data.get("streaks", {}).get(game_type, {"win_streak": 0, "lose_streak": 0})
    win_streak = streak_data.get("win_streak", 0)
    lose_streak = streak_data.get("lose_streak", 0)

    if is_win:
        win_streak += 1
        lose_streak = 0
    else:
        lose_streak += 1
        win_streak = 0

    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {f"streaks.{game_type}.win_streak": win_streak, f"streaks.{game_type}.lose_streak": lose_streak}},
        upsert=True
    )


def get_user_streaks(user_id: int, game_type: str) -> tuple[int, int]:
    """ゲームタイプごとのユーザーの連勝・連敗記録を取得"""
    user = users_collection.find_one({"user_id": user_id}, {"streaks": 1})
    
    if not user or "streaks" not in user:
        return 0, 0

    game_streaks = user.get("streaks", {}).get(game_type, {})
    return game_streaks.get("win_streak", 0), game_streaks.get("lose_streak", 0)


# ========================================
# ベット履歴管理
# ========================================
def update_bet_history(user_id: int, game_type: str, amount: int, is_win: bool) -> None:
    """ユーザーのベット履歴をデータベースに記録"""
    bet_entry = {
        "amount": amount,
        "is_win": bool(is_win),
        "timestamp": datetime.datetime.now()
    }

    bet_history_collection.update_one(
        {"user_id": user_id},
        {"$push": {f"bet_history.{game_type}.bets": bet_entry}},
        upsert=True
    )


# ========================================
# ユーザー登録
# ========================================
def register_user(user_id: int, sender_external_id: str) -> None:
    """新規ユーザーを登録"""
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {
            "sender_external_id": sender_external_id,
            "balance": 0
        }},
        upsert=True
    )

# ========================================
# トランザクション管理
# ========================================
def get_user_transactions(
    user_id: int,
    game_type: Optional[str] = None,
    days: Optional[int] = None
) -> list[dict[str, Any]]:
    """指定ユーザーの取引履歴を取得（オプションでゲーム種別や期間も絞れる）"""
    doc = user_transactions_collection.find_one({"user_id": user_id})

    if not doc or "transactions" not in doc:
        return []

    transactions = doc["transactions"]

    if game_type:
        transactions = [t for t in transactions if t.get("type") == game_type]

    if days:
        threshold = datetime.datetime.now() - timedelta(days=days)
        transactions = [t for t in transactions if t.get("timestamp") and t["timestamp"] >= threshold]

    return transactions


# ========================================
# ボット状態管理
# ========================================
async def save_account_panel_message_id(message_id: int) -> None:
    """アカウントパネルメッセージIDを保存"""
    bot_state_collection.update_one(
        {"_id": "account_panel"},
        {"$set": {"message_id": message_id}},
        upsert=True
    )


async def get_account_panel_message_id() -> Optional[int]:
    """アカウントパネルメッセージIDを取得"""
    doc = bot_state_collection.find_one({"_id": "account_panel"})
    return doc["message_id"] if doc and "message_id" in doc else None


# ========================================
# ユーザー一覧取得
# ========================================
def get_all_user_balances() -> list[tuple[int, int]]:
    """全ユーザーのuser_idと残高を取得する"""
    cursor = users_collection.find({}, {"user_id": 1, "balance": 1})
    return [(doc["user_id"], doc.get("balance", 0)) for doc in cursor]


# ========================================
# 招待管理
# ========================================
def get_user_invite(user_id: int) -> Optional[dict[str, Any]]:
    """ユーザーの招待情報を取得"""
    return invites_collection.find_one({"user_id": user_id})


def save_user_invite(user_id: int, url: str) -> None:
    """ユーザーの招待URLを保存"""
    invites_collection.update_one(
        {"user_id": user_id},
        {"$set": {"invite_url": url}},
        upsert=True
    )


def log_invited_user(invited_id: int, inviter_id: int, invite_code: str) -> None:
    """初参加ユーザーの招待ログを保存する"""
    invited_users_collection.insert_one({
        "invited_id": invited_id,
        "inviter_id": inviter_id,
        "invite_code": invite_code,
        "timestamp": datetime.datetime.utcnow()
    })


def get_invited_users(inviter_id: int) -> list[dict[str, Any]]:
    """招待したユーザー一覧を取得"""
    return list(invited_users_collection.find({"inviter_id": inviter_id}).sort("timestamp", -1))


def get_unredeemed_users(inviter_id: int) -> list[dict[str, Any]]:
    """未報酬の招待ユーザーを取得"""
    invited = invited_users_collection.find({"inviter_id": inviter_id})
    redeemed_ids = set(x["invited_id"] for x in invite_redeem_collection.find({"inviter_id": inviter_id}))
    return [doc for doc in invited if doc["invited_id"] not in redeemed_ids]


def mark_users_as_redeemed(inviter_id: int, invited_ids: list[int]) -> None:
    """招待ユーザーを報酬受領済みとしてマーク"""
    for invited_id in invited_ids:
        invite_redeem_collection.insert_one({
            "inviter_id": inviter_id,
            "invited_id": invited_id
        })


def has_already_been_invited(user_id: int) -> bool:
    """ユーザーが過去に一度でも招待されているかチェック"""
    return invited_users_collection.find_one({"invited_id": user_id}) is not None


def mark_user_as_invited(user_id: int) -> None:
    """ユーザーを招待済みとしてマーク"""
    invited_users_collection.insert_one({"user_id": user_id})


# ========================================
# 設定管理
# ========================================
def is_no_fee_mode_enabled() -> bool:
    """手数料無料モードが有効かチェック"""
    config_doc = payin_settings_collection.find_one({"_id": "conversion_rate"})
    return config_doc and config_doc.get("no_fee_mode", False)


# ========================================
# カジノテーブル管理
# ========================================
def save_casino_table(
    channel_id: int,
    category_id: int,
    table_number: int,
    channel_name: str,
    category_name: str
) -> None:
    """
    カジノテーブル情報をデータベースに保存
    
    Args:
        channel_id: チャンネルID
        category_id: カテゴリID
        table_number: テーブル番号
        channel_name: チャンネル名
        category_name: カテゴリ名
    """
    casino_tables_collection.insert_one({
        "channel_id": channel_id,
        "category_id": category_id,
        "table_number": table_number,
        "channel_name": channel_name,
        "category_name": category_name,
        "created_at": datetime.datetime.now()
    })


def get_all_casino_tables() -> list[dict[str, Any]]:
    """
    全カジノテーブル情報を取得
    
    Returns:
        テーブル情報のリスト
    """
    return list(casino_tables_collection.find({}))


def delete_casino_table(channel_id: int) -> None:
    """
    カジノテーブル情報をデータベースから削除
    
    Args:
        channel_id: チャンネルID
    """
    casino_tables_collection.delete_one({"channel_id": channel_id})


def clear_all_casino_tables() -> int:
    """
    全カジノテーブル情報をデータベースから削除
    
    Returns:
        削除された件数
    """
    result = casino_tables_collection.delete_many({})
    return result.deleted_count


def get_casino_table_count() -> int:
    """
    登録されているカジノテーブルの総数を取得
    
    Returns:
        テーブル数
    """
    return casino_tables_collection.count_documents({})