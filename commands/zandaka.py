import discord
from discord import app_commands
from database.db import users_collection, user_transactions_collection, get_user_balance
from bot import bot
from utils.embed import create_embed
import datetime

@bot.tree.command(name="zandaka", description="口座残高を表示")
async def zandaka(interaction: discord.Interaction):
    user_id = interaction.user.id
    user_info = users_collection.find_one({"user_id": user_id})

    if not user_info:
        embed = create_embed("", "あなたの口座は登録されていません。\n `/kouza` で口座を開設してください。", discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    balance = get_user_balance(user_id)
    embed = discord.Embed(title="口座残高", description=f"# {balance:,} PNC", color=discord.Color.green())
    user_transactions = user_transactions_collection.find_one({"user_id": user_id})
    transactions = user_transactions.get("transactions", [])[-5:]
    
    if transactions:
        history_text = ""
        for txn in reversed(transactions):
            type_emoji = "📥" if txn["type"] == "in" else "📤" if txn["type"] == "out" else "🔄"

            # `txn["timestamp"]` が `str` 型なら int に変換
            if isinstance(txn["timestamp"], str):
                txn["timestamp"] = int(txn["timestamp"])

            # `txn["timestamp"]` が `datetime.datetime` 型なら `strftime()` を適用
            if isinstance(txn["timestamp"], datetime.datetime):
                timestamp = txn["timestamp"].strftime('%Y-%m-%d %H:%M:%S')
            else:
                timestamp = datetime.datetime.fromtimestamp(txn["timestamp"] / 1000).strftime('%Y-%m-%d %H:%M:%S')

            history_text += f"{type_emoji} `{timestamp}` - `{txn['type'].capitalize()}`: `{txn['total']:,} PNC`\n"

        embed.add_field(name="**直近の取引履歴**", value=history_text, inline=False)
    else:
        embed.add_field(name="**直近の取引履歴**", value="取引履歴がありません。", inline=False)

    embed.set_footer(text=f"{interaction.user.display_name}様 | ID: {interaction.user.name}")

    await interaction.response.send_message(embed=embed, ephemeral=True)