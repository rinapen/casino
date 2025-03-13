import numpy as np
import xgboost as xgb
from database.db import users_collection, bet_history_collection
from models.xgb_model import load_model_from_mongodb

def get_dynamic_win_rate(game_type, base_rate, user_id):
    """プレイヤーごとの勝率をデータベースから取得して動的に調整"""

    user_data = users_collection.find_one({"user_id": user_id})
    bet_data = bet_history_collection.find_one({"user_id": user_id})

    if not user_data or not bet_data:
        print(f"[DEBUG] {user_id} のデータが不足。デフォルト勝率適用: {base_rate}%")
        return base_rate  

    total_bets = user_data.get("casino_stats", {}).get("total_bets", 1)
    total_wins = user_data.get("casino_stats", {}).get("total_wins", 0)
    user_win_rate = (total_wins / total_bets) * 100  

    bet_amounts = [bet.get("amount", 0) for bet in bet_data.get("bet_history", {}).get(game_type, {}).get("bets", [])]
    avg_bet = sum(bet_amounts) / len(bet_amounts) if bet_amounts else 100  

    win_streak = user_data.get("streaks", {}).get(game_type, {}).get("win_streak", 0)
    lose_streak = user_data.get("streaks", {}).get(game_type, {}).get("lose_streak", 0)
    current_streak = win_streak - lose_streak

    print(f"[DEBUG] {user_id} の現在の連勝: {win_streak}, 連敗: {lose_streak}, 現在の勝率: {user_win_rate}%")

    # **XGBoost モデルの使用**
    model = load_model_from_mongodb()
    if model:
        print("✅ AI モデルあり")
        features = np.array([[user_win_rate, avg_bet, base_rate]])
        dmatrix = xgb.DMatrix(features)  # ✅ `DMatrix` に変換
        predicted_win_rate = float(model.predict(dmatrix)[0])  # ✅ float に変換
    else:
        print("❌ AI モデルなし")
        predicted_win_rate = base_rate  

    print(f"[DEBUG] {user_id} の XGBoost 予測前勝率: {predicted_win_rate}%")

    # **連勝・連敗の影響を適用**
    if current_streak > 3:
        predicted_win_rate -= 5
    elif current_streak < -3:
        predicted_win_rate += 5

    # **高額ベットなら勝率を下げる**
    if avg_bet > 500:
        predicted_win_rate -= 3

    # **勝率の範囲を 5% ~ 95% に制限**
    adjusted_win_rate = max(5, min(95, predicted_win_rate))

    print(f"[DEBUG] {user_id} の最終勝率: {adjusted_win_rate:.2f}%")
    return adjusted_win_rate