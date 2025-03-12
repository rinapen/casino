import discord
from discord import app_commands
from database import log_transaction, get_user_balance, update_user_balance, users_collection
from paypay_session import paypay_session
from config import MIN_INITIAL_DEPOSIT
from bot import bot
from decimal import Decimal, ROUND_HALF_UP
from utils import create_embed

@bot.tree.command(name="payout", description="指定した額を引き出し（PayPayに送金）")
@app_commands.describe(amount="出金額（手数料は自動計算）")
async def payout(interaction: discord.Interaction, amount: int):
    user_id = interaction.user.id
    sender_info = users_collection.find_one({"user_id": user_id})

    if sender_info is None or "sender_external_id" not in sender_info:
        embed = create_embed("", "あなたの口座が見つかりません。\n `/kouza` で口座を開設してください。", discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    sender_external_id = sender_info["sender_external_id"]
    user_balance = get_user_balance(user_id)

    if user_balance is None or user_balance < MIN_INITIAL_DEPOSIT:
        embed = create_embed(
            "",
            f"出金するには最低 `{MIN_INITIAL_DEPOSIT:,} PNC` の残高が必要です。",
            discord.Color.yellow()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    max_withdrawable = (Decimal(user_balance) / (Decimal(1) + Decimal(0.14))).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    if amount > max_withdrawable:
        embed = create_embed(
            "",
            f"現在の最大出金可能額は `{int(max_withdrawable):,} PNC` です。",
            discord.Color.yellow()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    fee = max((Decimal(amount) * Decimal(0.14)).quantize(Decimal("1"), rounding=ROUND_HALF_UP), Decimal(10))
    total_deduction = amount + fee 

    if user_balance < total_deduction:
        embed = create_embed(
            "",
            f"手数料込みで `{int(total_deduction):,} PNC` が必要ですが、残高が不足しています。",
            discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    paypay_session.send_money(int(amount), sender_external_id)

    update_user_balance(user_id, -int(total_deduction))
    log_transaction(user_id, "out", int(amount), int(fee), int(total_deduction), sender_external_id)

    embed = discord.Embed(title="出金完了", color=discord.Color.green())
    embed.add_field(name="出金額", value=f"`{int(amount):,}円`", inline=False)
    embed.add_field(name="手数料", value=f"`{int(fee):,}円`", inline=False)
    embed.add_field(name="合計引き落とし", value=f"`{int(total_deduction):,} PNC`", inline=False)
    embed.add_field(name="出金先", value=f"`{sender_external_id}`", inline=False)
    embed.add_field(name="最大出金可能額", value=f"`{int(max_withdrawable):,} PNC`", inline=False)
    embed.set_footer(text=f"現在の残高: {get_user_balance(user_id):,} PNC")

    await interaction.response.send_message(embed=embed, ephemeral=True)
