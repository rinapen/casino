import discord
import re
from discord import app_commands
from database.db import update_user_balance, register_user, users_collection, user_transactions_collection
from paypay_session import paypay_session
from config import MIN_INITIAL_DEPOSIT, PAYPAY_ICON_URL, PAYPAY_LINK_REGEX
from bot import bot
from decimal import Decimal, ROUND_HALF_UP
from PayPaython_mobile.main import PayPayError
from utils.logs import send_paypay_log
from utils.embed import create_embed
from utils.stats import log_transaction

@bot.tree.command(name="kouza", description="口座を開設")
async def kouza(interaction: discord.Interaction):
    modal = RegisterModal()
    await interaction.response.send_modal(modal)

class RegisterModal(discord.ui.Modal, title="口座開設"):
    def __init__(self):
        super().__init__()
        self.username = discord.ui.TextInput(label="名前(適当でいい)", placeholder="例: べるざべす")
        # self.password = discord.ui.TextInput(label="パスワード", placeholder="パスワード", style=discord.TextStyle.short)
        self.deposit_link = discord.ui.TextInput(label="入金リンク（最低 116 pay 必須）", placeholder="PayPay送金リンクを入力")
        self.add_item(self.username)
        # self.add_item(self.password)
        self.add_item(self.deposit_link)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        discord_user = interaction.user
        await interaction.response.defer(ephemeral=True)

        if users_collection.find_one({"user_id": user_id}):
            embed = create_embed("", "あなたはすでに口座を開設しています。", discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if not re.match(PAYPAY_LINK_REGEX, self.deposit_link.value):
            embed = create_embed("", "無効なリンクです。有効な PayPay リンクを入力してください。", discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            deposit_info = paypay_session.paypay.link_check(self.deposit_link.value)
            amount = Decimal(deposit_info.amount)
        except PayPayError as e:
            error_code = e.args[0].get("error", {}).get("backendResultCode", "不明")
            error_msg = "このリンクはすでに使用済みです。" if error_code == "02100029" else f"エラーコード: `{error_code}`"
            embed = create_embed("", f"PayPayリンクの確認中にエラーが発生しました。\n{error_msg}", discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        fee = max((amount * Decimal(0.14)).quantize(Decimal("1"), rounding=ROUND_HALF_UP), Decimal(10))
        net_amount = amount - fee

        if amount < (Decimal(MIN_INITIAL_DEPOSIT) + fee):
            embed = create_embed("", f"最低 `{int(MIN_INITIAL_DEPOSIT + fee):,} PNC` が必要です。", discord.Color.yellow())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        user = paypay_session.paypay.link_receive(self.deposit_link.value)
        user_transactions_collection.insert_one({
            "user_id": user_id,
            "transactions": []
        })
        register_user(user_id,  self.username.value, deposit_info.sender_external_id)
        update_user_balance(user_id, int(net_amount))
        log_transaction(
            user_id=user_id,
            game_type="payin",
            amount=int(amount),
            payout=int(net_amount)
        )
        embed = discord.Embed(title="口座開設完了", color=discord.Color.green())
        embed.set_author(name="PayPay",icon_url=PAYPAY_ICON_URL)
        # embed.set_image(url=profile.icon)
        embed.add_field(name="入金額", value=f"`{int(amount):,}円`", inline=False)
        embed.add_field(name="手数料", value=f"`{int(fee):,}円`", inline=False)
        embed.add_field(name="初期残高", value=f"`{int(net_amount):,} PNC`", inline=False)
        embed.add_field(name="決済番号", value=f"`{deposit_info.order_id}`")
        # embed.add_field(name="支払い状況", value=f"{deposit_info.status}")
        embed.set_footer(text=f"{deposit_info.sender_name} 様", icon_url=deposit_info.sender_icon)
        await interaction.followup.send(embed=embed, ephemeral=True)
        await send_paypay_log(discord_user, amount, fee, net_amount, is_register=True)