import discord
from discord import app_commands
from database import transactions_collection
from bot import bot 

def create_embed(title, description, color):
    embed = discord.Embed(title=title, description=description, color=color)
    return embed

@bot.tree.command(name="rireki", description="取引明細を表示")
async def rireki(interaction: discord.Interaction):
    user_id = interaction.user.id
    transactions = list(transactions_collection.find({"user_id": user_id}).sort("timestamp", -1).limit(5))

    if not transactions:
        embed = create_embed("取引履歴", "取引履歴がありません。", discord.Color.dark_gray())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    embed = discord.Embed(title="取引履歴", color=discord.Color.blue())

    for txn in transactions:
        type_emoji = "📥" if txn["type"] == "in" else "📤" if txn["type"] == "out" else "🔄"

        receiver_text = f"**送金先**: `{txn['receiver']}`" if txn.get("receiver") else ""

        embed.add_field(
            name=f"{type_emoji} `{txn['type'].capitalize()}` - `{txn['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}`",
            value=f"**金額**: `{txn['amount']} pnc`\n"
                  f"**手数料**: `{txn['fee']} pnc`\n"
                  f"**合計**: `{txn['total']} pnc`\n"
                  f"{receiver_text}",
            inline=False
        )

    embed.set_footer(text=f"{interaction.user.display_name}様 | ID: {interaction.user.name}")

    await interaction.response.send_message(embed=embed, ephemeral=True)