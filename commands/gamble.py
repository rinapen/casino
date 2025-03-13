import discord
import random
from discord import app_commands
from bot import bot
from database.db import get_user_balance, update_user_balance, update_user_streak, get_user_streaks, update_bet_history
from utils.win_rate import get_dynamic_win_rate
from utils.logs import send_casino_log
from config import WIN_EMOJI, LOSE_EMOJI

VALID_MULTIPLIERS = [2, 3]
VALID_BETS = [500, 1000]

@bot.tree.command(name="gamble", description="2倍 or 3倍のギャンブルゲーム")
@app_commands.describe(multiplier="2倍 or 3倍を選択", amount="ベット額を選択")
@app_commands.choices(multiplier=[
    app_commands.Choice(name="2倍", value=2),
    app_commands.Choice(name="3倍", value=3)
])
@app_commands.choices(amount=[
    app_commands.Choice(name="500 PNC", value=500),
    app_commands.Choice(name="1000 PNC", value=1000)
])
async def gamble(interaction: discord.Interaction, multiplier: int, amount: int):
    user_id = interaction.user.id
    balance = get_user_balance(user_id)

    if balance is None or balance < amount:
        embed = discord.Embed(title="❌ エラー", description="残高が不足しています。", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    base_win_rate = 47 if multiplier == 2 else 28.57

    # 🔹 **ユーザーの連勝・連敗データを取得**
    win_streak, lose_streak = get_user_streaks(user_id, "gamble")

    # 🔹 **高額ベットによる勝率調整**
    if amount == 1000:
        base_win_rate -= 5  
    base_win_rate -= win_streak * 3  
    base_win_rate += lose_streak * 3  
    base_win_rate = max(5, min(95, base_win_rate))  # 5% 〜 95% の範囲に制限

    # 🔹 **動的勝率を取得**
    win_rate = get_dynamic_win_rate("gamble", base_win_rate, user_id)
    print(f"[DEBUG] {user_id} の最終勝率: {win_rate:.2f}%")

    # 🔹 **結果の判定**
    is_win = random.uniform(0, 100) <= win_rate
    update_user_balance(user_id, -amount)  # **まずベット額を引く**

    if is_win:
        winnings = amount * multiplier
        update_user_balance(user_id, winnings)
        update_user_streak(user_id, "gamble", True)
        result_text = f"✅ **勝利！** `{winnings} PNC` を獲得しました。"
        color = discord.Color.green()
        emoji = WIN_EMOJI
    else:
        winnings = 0
        update_user_streak(user_id, "gamble", False)
        result_text = f"❌ **敗北…** `{amount} PNC` を失いました。"
        color = discord.Color.red()
        emoji = LOSE_EMOJI

    # 🔹 **ベット履歴をデータベースに記録**
    update_bet_history(user_id, "gamble", amount, is_win)

    # 🔹 **カジノログを送信**
    await send_casino_log(interaction, emoji, amount, "", color)

    # 🔹 **結果を表示**
    balance = get_user_balance(user_id)
    embed = discord.Embed(title="ギャンブル結果", description=result_text, color=color)
    embed.add_field(name="**ベット額**", value=f"`{amount} PNC`", inline=False)
    embed.add_field(name="**倍率**", value=f"`{multiplier}x`", inline=False)
    embed.set_footer(text=f"現在の残高: {balance} PNC")

    await interaction.response.send_message(embed=embed)
