import discord
import random
from discord import app_commands
from bot import bot
from database.db import get_user_balance, update_user_balance, update_user_streak, get_user_streaks
from utils.embed import create_embed
from utils.logs import send_casino_log
from utils.win_rate import get_dynamic_win_rate
from config import WIN_EMOJI, LOSE_EMOJI

VALID_BETS = {
    "red": "🔴",
    "black": "⚫",
    "green": "🟢"
}

MIN_BET = 25

BET_PENALTY = {
    25: 0,
    50: -1.0,
    100: -2.0,
    200: -3.5,
    500: -5.5,
    1000: -8.0
}

BASE_WIN_RATE = {
    "red": 43,  # 45% → 43%（微調整）
    "black": 43,  # 45% → 43%（微調整）
    "green": 2.0  # 1.5% → 2.0%（微調整）
}

@bot.tree.command(name="roulette", description="ルーレットで賭ける")
@app_commands.describe(bet="ベットする色を選択", amount="賭ける金額を選択")
@app_commands.choices(bet=[
    app_commands.Choice(name="🔴 x2", value="red"),
    app_commands.Choice(name="⚫ x2", value="black"),
    app_commands.Choice(name="🟢 x14", value="green")
])
@app_commands.choices(amount=[
    app_commands.Choice(name="25 PNC", value=25),
    app_commands.Choice(name="50 PNC", value=50),
    app_commands.Choice(name="100 PNC", value=100),
    app_commands.Choice(name="200 PNC", value=200),
    app_commands.Choice(name="500 PNC", value=500),
    app_commands.Choice(name="1000 PNC", value=1000)
])
async def roulette(interaction: discord.Interaction, bet: str, amount: int):
    user_id = interaction.user.id
    user_balance = get_user_balance(user_id)

    if user_balance is None or user_balance < amount:
        embed = create_embed("❌ 残高不足", f"現在の残高は `{user_balance:,} PNC` です。\nベット額を減らしてください。", discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if amount < MIN_BET:
        embed = create_embed("⚠ 最低ベット額", f"最低 `{MIN_BET} PNC` 以上のベットが必要です。", discord.Color.yellow())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # 🔹 **連勝・連敗データを取得**
    win_streak, lose_streak = get_user_streaks(user_id, "roulette")

    # 🔹 **基本勝率を取得**
    base_win_rate = BASE_WIN_RATE[bet]

    # 🟢 **緑の勝率は最大2.0%固定（変動なし）**
    if bet == "green":
        win_rate = base_win_rate
    else:
        win_rate = get_dynamic_win_rate("roulette", base_win_rate, user_id)
        win_rate += BET_PENALTY[amount]  # **ベット額の影響を反映**
        win_rate -= win_streak * 5  # **連勝時に勝率を大幅ダウン**
        win_rate += lose_streak * 2  # **負け続けてもあまり影響なし**
        win_rate = max(0, min(win_rate, 100))

    # 🔹 **ルーレット結果を決定**
    is_win = random.uniform(0, 100) <= win_rate
    update_user_balance(user_id, -amount)  # **ベット額を引く**

    if is_win:  # **勝ち**
        result = VALID_BETS[bet]
        payout = amount * (14 if bet == "green" else 2)
        update_user_balance(user_id, payout)  # **運営利益を引かずそのまま**
        update_user_streak(user_id, "roulette", True)  # **勝ち streak を更新**
        emoji = WIN_EMOJI
        color = discord.Color.green()
        result_text = f"✅ **勝利！** {result}"
        log_amount = payout - amount
    else:  # **負け**
        if bet == "red":
            result = random.choices(["⚫", "🟢"], weights=[97, 3])[0]
        elif bet == "black":
            result = random.choices(["🔴", "🟢"], weights=[97, 3])[0]
        else:
            result = random.choices(["🔴", "⚫"], weights=[99, 1])[0]  # **緑の勝率をさらに減らす**

        update_user_streak(user_id, "roulette", False)  # **負け streak を更新**
        emoji = LOSE_EMOJI
        color = discord.Color.red()
        result_text = f"❌ **敗北...** {result}"
        log_amount = amount

    embed = create_embed("ルーレット結果", f"ルーレットの結果: {result_text}", color)
    embed.add_field(name="**ベット**", value=f"`{VALID_BETS[bet]}`", inline=False)
    embed.add_field(name="**ベット額**", value=f"`{amount} PNC`", inline=False)

    if is_win:
        embed.add_field(name="✅ **獲得**", value=f"`{log_amount} PNC`", inline=False)
        await send_casino_log(interaction, emoji, log_amount, "", color)
    else:
        embed.add_field(name="❌ **損失**", value=f"`{amount} PNC`", inline=False)
        await send_casino_log(interaction, emoji, amount, "", color)

    embed.set_footer(text=f"現在の残高: {get_user_balance(user_id)} PNC")

    await interaction.response.send_message(embed=embed)