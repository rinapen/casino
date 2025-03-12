import discord
import re
from discord import app_commands
from database import log_transaction, update_user_balance, get_user_balance, users_collection
from paypay_session import paypay_session
from config import MIN_INITIAL_DEPOSIT, PAYPAY_LINK_REGEX
from bot import bot
from decimal import Decimal, ROUND_HALF_UP
from PayPaython_mobile.main import PayPayError
from utils import send_paypay_log, create_embed

@bot.tree.command(name="payin", description="自分の口座に残高を追加")
@app_commands.describe(link="PayPayリンクを入力してください")
async def payin(interaction: discord.Interaction, link: str):
    user_id = interaction.user.id
    user = interaction.user
    user_info = users_collection.find_one({"user_id": user_id})

    if not user_info:
        embed = create_embed("", "あなたの口座が見つかりません。\n `/kouza` で口座を開設してください。", discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if not re.match(PAYPAY_LINK_REGEX, link):
        embed = create_embed("", "無効なリンクです。有効な PayPay リンクを入力してください。", discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    try:
        link_info = paypay_session.paypay.link_check(link)
        print(f"DEBUG: Link Status - {link_info.status}") 

        if link_info.status in ["COMPLETED", "REJECTED", "FAILED"]:
            embed = create_embed("", "このリンクはすでに使用済み、または無効です。", discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        amount = Decimal(link_info.amount)

    except PayPayError as e:
        error_code = e.args[0].get("error", {}).get("backendResultCode", "不明")
        error_msg = f"エラーコード: `{error_code}`"
        embed = create_embed("", f"PayPayリンクの確認中にエラーが発生しました。\n{error_msg}", discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    fee = max((amount * Decimal(0.14)).quantize(Decimal("1"), rounding=ROUND_HALF_UP), Decimal(10))
    net_amount = amount - fee 

    if amount < (Decimal(MIN_INITIAL_DEPOSIT) + fee):
        embed = create_embed("", f"最低入金額は `{int(MIN_INITIAL_DEPOSIT + fee):,} PNC` です。", discord.Color.yellow())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    try:
        paypay_session.paypay.link_receive(link)

        update_user_balance(user_id, int(net_amount))
        log_transaction(user_id, "in", int(amount), int(fee), int(net_amount))

        embed = discord.Embed(title="入金完了", color=discord.Color.green())
        embed.add_field(name="入金額", value=f"`{int(amount):,}円`", inline=True)
        embed.add_field(name="手数料", value=f"`{int(fee):,}円`", inline=True)
        embed.add_field(name="現在の残高", value=f"`{get_user_balance(user_id):,} PNC`", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)
        await send_paypay_log(user, amount, fee, net_amount)

    except PayPayError as e:
        embed = create_embed("", "入金処理中にエラーが発生しました。\nこのリンクはすでに使用済み、または無効です。", discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)