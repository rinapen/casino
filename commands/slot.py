import discord
import random
from discord import app_commands
from database.db import get_user_balance, update_user_balance
from bot import bot
from utils.logs import send_casino_log
from config import WIN_EMOJI, LOSE_EMOJI

SLOT_SYMBOLS = ["🍒", "🍋", "🍊", "🍉", "⭐", "💎"]
PAYOUTS = {
    "🍒": 2,
    "🍋": 3,
    "🍊": 4,
    "🍉": 5,
    "⭐": 10,
    "💎": 50  
}

SLOT_WEIGHTS = {
    "🍒": 40,  # 40% の確率
    "🍋": 25,  # 25% の確率
    "🍊": 15,  # 15% の確率
    "🍉": 10,  # 10% の確率
    "⭐": 5,   # 5% の確率
    "💎": 1    # 1% の確率（超レア）
}

# **確率テーブルを作成**
WEIGHTED_SYMBOLS = [symbol for symbol, weight in SLOT_WEIGHTS.items() for _ in range(weight)]

# **ベット可能な金額**
VALID_BETS = [50, 100, 200, 500, 1000]

@bot.tree.command(name="slot", description="スロットを回して勝負！")
@app_commands.describe(amount="ベット額を選択")
@app_commands.choices(amount=[
    app_commands.Choice(name="50 PNC", value=50),
    app_commands.Choice(name="100 PNC", value=100),
    app_commands.Choice(name="200 PNC", value=200),
    app_commands.Choice(name="500 PNC", value=500),
    app_commands.Choice(name="1000 PNC", value=1000)
])
async def slot(interaction: discord.Interaction, amount: int):
    user_id = interaction.user.id
    balance = get_user_balance(user_id)

    if balance is None or balance < amount:
        embed = discord.Embed(title="❌ エラー", description="残高が不足しています。", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # **ユーザー残高からベット額を差し引く**
    update_user_balance(user_id, -amount)

    # **スロットの回転結果**
    slot_result = [random.choice(WEIGHTED_SYMBOLS) for _ in range(3)]
    result_text = " | ".join(slot_result)

    if slot_result[0] == slot_result[1] == slot_result[2]:  # **3つ揃い（勝利）**
        multiplier = PAYOUTS.get(slot_result[0], 1)  
        winnings = amount * multiplier
        update_user_balance(user_id, winnings)  # **勝った分だけ加算**
        # log_transaction(user_id, "slot_win", amount, 0, winnings - amount)  # **純利益をログ**
    else:  # **ハズレ**
        winnings = 0
        # log_transaction(user_id, "slot_loss", amount, 0, -amount)

    # **Embed の色と絵文字**
    color = discord.Color.green() if winnings > 0 else discord.Color.red()
    emoji = WIN_EMOJI if winnings > 0 else LOSE_EMOJI

    # **結果の Embed メッセージ**
    embed = discord.Embed(title="🎰 スロット結果", color=color)
    embed.add_field(name="**結果**", value=f"`{result_text}`", inline=False)
    embed.add_field(name="💰 **ベット額**", value=f"`{amount} PNC`", inline=True)

    if winnings > 0:
        embed.add_field(name="✅ **獲得**", value=f"`{winnings - amount} PNC`", inline=True)  # **純利益を表示**
        await send_casino_log(interaction, emoji, winnings - amount, "", color)
    else:
        embed.add_field(name="❌ **損失**", value=f"`{amount} PNC`", inline=True)
        await send_casino_log(interaction, emoji, amount, "", color)

    embed.set_footer(text=f"現在の残高: {get_user_balance(user_id)} PNC")
    await interaction.response.send_message(embed=embed)

def adjust_slot_weights(bet):
    """ベット額が大きいほど高配当シンボルが出にくくする"""
    weight_multiplier = 1 - min(bet / 2000, 0.3)  # 最大30%カット

    adjusted_weights = {symbol: int(weight * weight_multiplier) for symbol, weight in SLOT_WEIGHTS.items()}
    return adjusted_weights

def spin_slot(bet):
    """スロットを回す（ベット額に応じた確率調整）"""
    weights = adjust_slot_weights(bet)
    weighted_symbols = [symbol for symbol, weight in weights.items() for _ in range(weight)]
    return [random.choice(weighted_symbols) for _ in range(3)]
