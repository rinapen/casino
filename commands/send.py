import discord
from discord import app_commands
from bot import bot
from database import get_user_balance, update_user_balance, log_transaction, users_collection
from config import TAX_RATE, FEE_RATE

def create_embed(title, description, color):
    embed = discord.Embed(title=title, description=description, color=color)
    return embed

@bot.tree.command(name="send", description="他のユーザーに送金")
@app_commands.describe(amount="送金額", recipient="送金相手のユーザー")
async def send(interaction: discord.Interaction, amount: int, recipient: discord.Member):
    user_id = interaction.user.id
    recipient_id = recipient.id

    if user_id == recipient_id:
        embed = create_embed("", "自分自身には送金できません。", discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    sender_info = users_collection.find_one({"user_id": user_id})
    recipient_info = users_collection.find_one({"user_id": recipient_id})

    if not sender_info:
        embed = create_embed("", "送金するにはまず `/kouza` で口座を開設してください。", discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if not recipient_info:
        embed = create_embed("", f"受取人 `{recipient.display_name}({recipient.name})` の口座が存在しません。", discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    sender_balance = get_user_balance(user_id)

    fee = int(amount * (TAX_RATE + FEE_RATE))
    total_deduction = amount + fee 

    if sender_balance < total_deduction:
        embed = create_embed(
            "",
            f"送金には `{total_deduction:,} pnc` が必要ですが、現在の残高は `{sender_balance:,} pnc` です。",
            discord.Color.yellow()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    update_user_balance(user_id, -total_deduction) 
    update_user_balance(recipient_id, amount)  
    log_transaction(user_id, "send", amount, fee, total_deduction, recipient_id)

    embed = discord.Embed(title="送金完了", color=discord.Color.green())
    embed.add_field(name="**送金額**", value=f"`{amount:,} pnc`", inline=True)
    embed.add_field(name="**手数料**", value=f"`{fee:,} pnc`", inline=True)
    embed.add_field(name="**合計引き落とし**", value=f"`{total_deduction:,} pnc`", inline=False)
    embed.add_field(name="**受取人**", value=f"`{recipient.display_name}({recipient.name})`", inline=False)
    embed.set_footer(text=f"現在の残高: {get_user_balance(user_id):,} pnc")

    await interaction.response.send_message(embed=embed, ephemeral=True)