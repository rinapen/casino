import discord
from discord.ext import tasks
import pytz
from datetime import time, datetime
import os
import json
from collections import defaultdict

from database.db import user_transactions_collection
from bot import bot

from utils.bot_state import save_last_message_id_to_db, get_last_message_id_from_db
from utils.emojis import PNC_EMOJI_STR

from config import RANKING_CHANNEL_ID

JST = pytz.timezone("Asia/Tokyo")

STORAGE_PATH = "last_monthly_ranking.json"

def save_last_message_id(message_id):
    with open(STORAGE_PATH, "w") as f:
        json.dump({"message_id": message_id}, f)

def get_last_message_id():
    if not os.path.exists(STORAGE_PATH):
        return None
    with open(STORAGE_PATH, "r") as f:
        data = json.load(f)
    return data.get("message_id")

@tasks.loop(time=[time(hour=0, minute=0, tzinfo=JST), time(hour=12, minute=0, tzinfo=JST)])
async def send_monthly_usage_ranking():
    await send_or_update_ranking()

JST = pytz.timezone("Asia/Tokyo")

async def send_or_update_ranking():
    try:
        now = datetime.now(JST)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now

        excluded_user_id = 1154344959646908449
        target_user_id = 1154344959646908449
        target_payin_total = 0

        total_payin = 0  # 全体Payin合計
        total_payout = 0  # 全体Payout合計

        cursor = user_transactions_collection.find({
            "transactions.timestamp": {"$gte": start, "$lt": end}
        })

        user_profits = defaultdict(int)

        for doc in cursor:
            user_id = doc["user_id"]

            for txn in doc.get("transactions", []):
                ts = txn.get("timestamp")
                if ts is None:
                    continue

                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))

                try:
                    ts_jst = ts.astimezone(JST)
                except Exception as e:
                    print(f"[WARN] timestamp変換エラー: {e}")
                    continue

                if start <= ts_jst < end:
                    tx_type = txn.get("type")
                    amount = txn.get("amount", 0)

                    if user_id == target_user_id and tx_type == "payin":
                        target_payin_total += amount
                        print(f"[DEBUG] 対象ユーザーのPayin: {amount}")

                    if user_id == excluded_user_id:
                        continue

                    if tx_type == "payin":
                        user_profits[user_id] += amount
                        total_payin += amount
                    elif tx_type == "payout":
                        user_profits[user_id] -= amount * 10
                        total_payout += amount

        ranking = sorted(user_profits.items(), key=lambda x: x[1], reverse=True)[:10]
        if not ranking:
            print("[LOG] 月間ランキングデータなし")
            return

        label = start.strftime('%Y年%m月')
        embed = discord.Embed(
            title="🏆 月間貢献ランキング",
            description=f"**{label} のトップユーザー**",
            color=discord.Color.orange()
        )

        for i, (uid, profit) in enumerate(ranking, start=1):
            try:
                user = await bot.fetch_user(uid)
                name = user.display_name
            except Exception as e:
                print(f"[WARN] ユーザー取得失敗: {e}")
                name = f"Unknown({uid})"

            embed.add_field(
                name=f"{i}位：{name}",
                value=f"<@{uid}>：{PNC_EMOJI_STR}`{profit * 10:,}`",
                inline=False
            )

        embed.set_footer(text="⏳ 自動送信 - 月間利益ランキング")

        channel = bot.get_channel(int(RANKING_CHANNEL_ID))
        if not channel:
            print("[ERROR] チャンネルが見つかりません")
            return

        try:
            message_id = await get_last_message_id_from_db()
            print(f"[DEBUG] 前回のメッセージID: {message_id}")
            if message_id:
                try:
                    old_msg = await channel.fetch_message(message_id)
                    await old_msg.delete()
                    print(f"[LOG] 旧ランキングを削除: {message_id}")
                except Exception as e:
                    print(f"[WARN] 旧メッセージの取得・削除に失敗: {e}")
            else:
                print("[INFO] 前回のランキングメッセージIDがDBに存在しません（初回送信）")
        except Exception as e:
            print(f"[ERROR] メッセージID取得失敗: {e}")

        try:
            new_msg = await channel.send(embed=embed)
            await save_last_message_id_to_db(new_msg.id)
            print(f"[LOG] 新ランキング送信: {new_msg.id}")
        except Exception as e:
            print(f"[ERROR] ランキング送信失敗: {e}")

    except Exception as e:
        print(f"[FATAL] send_or_update_ranking 全体エラー: {e}")