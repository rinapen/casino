import datetime
from database.db import get_user_transactions, user_transactions_collection

def get_user_net_profit(user_id: int, game: str = "roulette", days: int = None) -> int:
    """ユーザーの総損益を取得（負けてるとマイナス）"""
    logs = get_user_transactions(user_id, game, days)
    return sum(log.get("net", 0) for log in logs)

def log_transaction(user_id: int, game_type: str, amount: int, payout: int):
    """
    ユーザーのゲーム損益をログとして記録
    - amount: ベットした金額
    - payout: 実際に払い戻された金額（勝ちなら報酬、負けなら0）
    """
    net = payout - amount
    transaction = {
        "type": game_type,
        "mode": "win" if net > 0 else "loss",
        "amount": amount,
        "payout": payout,
        "net": net,
        "timestamp": datetime.datetime.now()
    }

    user_transactions_collection.update_one(
        {"user_id": user_id},
        {"$push": {"transactions": transaction}},
        upsert=True
    )