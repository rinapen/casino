import discord
import re
from decimal import Decimal, ROUND_HALF_UP
import traceback

from paypay_session import paypay_session
from PayPaython_mobile.main import PayPayError

from database.db import (
    update_user_balance,
    get_user_balance,
    register_user,
    users_collection,
    active_users_collection,
)
from config import (
    PAYPAY_LINK_REGEX,
    MIN_INITIAL_DEPOSIT,
)
from utils.embed import create_embed
from utils.pnc import jpy_to_pnc, pnc_to_jpy
from utils.logs import send_paypay_log, log_transaction
from utils.emojis import PNC_EMOJI_STR

class LinkInputModal(discord.ui.Modal, title="送金リンクを入力"):
    def __init__(self, user_id: int, expected_amount: Decimal):
        super().__init__()
        self.user_id = user_id
        self.expected_amount = expected_amount
        self.link_input = discord.ui.TextInput(
            label="PayPayリンク",
            placeholder="https://paypay.ne.jp/...",
            required=True
        )
        self.add_item(self.link_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = self.user_id
        expected_amount = self.expected_amount
        paypay_link = self.link_input.value.strip()
        await interaction.response.defer(ephemeral=True)

        link_match = re.search(PAYPAY_LINK_REGEX, paypay_link)
        if not link_match:
            await interaction.followup.send(
                embed=create_embed(
                    "❌ 無効なリンク",
                    "正しいPayPayリンクを入力してください。\n例: https://paypay.ne.jp/...",
                    discord.Color.red()
                ),
                ephemeral=True
            )
            return

        paypay_link = link_match.group(0).strip()
        print(paypay_link)
        try:
            deposit_info = paypay_session.paypay.link_check(paypay_link)
            jpy_amount = Decimal(deposit_info.amount)

            if jpy_amount != expected_amount:
                await interaction.followup.send(
                    embed=create_embed(
                        "❌ 金額不一致",
                        f"### 指定された金額は **{expected_amount}**円ですが、リンクの金額は **{jpy_amount}**円でした。",
                        discord.Color.red()
                    ),
                    ephemeral=True
                )
                return

            sender_id = deposit_info.sender_external_id
            existing = users_collection.find_one({"user_id": user_id})

            if existing:
                if existing.get("sender_external_id") != sender_id:
                    admin_user = await interaction.client.fetch_user(1154344959646908449)
                    await admin_user.send(f"⚠️ ユーザー <@{user_id}> が異なる sender_external_id で登録を試みました。")
                    await interaction.followup.send(
                        embed=create_embed(
                            "⚠️ エラーが発生しました",
                            "登録情報と一致しませんでした。管理者にお問い合わせください。",
                            discord.Color.red()
                        ),
                        ephemeral=True
                    )
                    return

                await interaction.followup.send(
                    embed=create_embed("✅ 認証成功", "送信者情報が一致しました。", discord.Color.green()),
                    ephemeral=True
                )
            else:
                active_data = active_users_collection.find_one({"user_id": user_id})
                restored_balance = int(active_data["balance"]) if active_data and "balance" in active_data else 0

                register_user(user_id, sender_id)
                update_user_balance(user_id, restored_balance)

                await interaction.followup.send(
                    embed=create_embed("✅ 登録完了", "登録が正常に完了しました。", discord.Color.green()),
                    ephemeral=True
                )

        except PayPayError as e:
            print("[PayPayError]", e)
            await interaction.followup.send(
                embed=create_embed(
                    "❌ リンク確認エラー",
                    f"リンクが無効か、すでに使用済みです。",
                    discord.Color.red()
                ),
                ephemeral=True
            )
        except Exception as e:
            print("[ERROR] 登録処理で例外が発生しました:", e)
            traceback.print_exc()
            await interaction.followup.send(
                embed=create_embed(
                    "⚠️ 不明なエラー",
                    "予期せぬエラーが発生しました。管理者にお問い合わせください。",
                    discord.Color.red()
                ),
                ephemeral=True
            )

class PayinModal(discord.ui.Modal, title="入金"):
    def __init__(self):
        super().__init__()
        self.link = discord.ui.TextInput(label="PayPayリンク", placeholder="PayPay送金リンクを入力")
        self.add_item(self.link)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        user = interaction.user
        await interaction.response.defer(ephemeral=True)

        existing = users_collection.find_one({"user_id": user_id})
        if not existing:
            embed = create_embed("", "あなたの口座が見つかりません。\n `/kouza` で口座を開設してください。", discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        link_match = re.search(PAYPAY_LINK_REGEX, self.link.value)
        if not link_match:
            embed = create_embed("", "無効なリンクです。有効な PayPay リンクを入力してください。", discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        paypay_link = link_match.group(0).strip()

        try:
            link_info = paypay_session.paypay.link_check(paypay_link)
            if link_info.status in ["COMPLETED", "REJECTED", "FAILED"]:
                embed = create_embed("", "このリンクはすでに使用済み、または無効です。", discord.Color.red())
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            sender_id = link_info.sender_external_id
            if existing.get("sender_external_id") != sender_id:
                admin_user = await interaction.client.fetch_user(1154344959646908449)
                await admin_user.send(f"⚠️ ユーザー <@{user_id}> が延長時に異なる sender_external_id を使用しました。")

                embed = create_embed(
                    "⚠️ セキュリティエラー",
                    "送金リンクが登録情報と一致しませんでした。\n管理者までご連絡ください。",
                    discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            jpy_amount = Decimal(link_info.amount)

        except PayPayError as e:
            error_code = e.args[0].get("error", {}).get("backendResultCode", "不明")
            embed = create_embed("", f"PayPayリンク確認中にエラー発生。\nコード: `{error_code}`", discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        total_pnc = jpy_to_pnc(jpy_amount)
        fee_jpy = max((jpy_amount * Decimal("0.14")).quantize(Decimal("1"), rounding=ROUND_HALF_UP), Decimal(10))
        fee_pnc = jpy_to_pnc(fee_jpy)
        net_pnc = total_pnc - fee_pnc

        gross_min_jpy = pnc_to_jpy(MIN_INITIAL_DEPOSIT)
        min_fee_jpy = max((gross_min_jpy * Decimal("0.14")).quantize(Decimal("1"), rounding=ROUND_HALF_UP), Decimal(10))
        required_jpy = gross_min_jpy + min_fee_jpy

        if jpy_amount < required_jpy:
            shortfall = required_jpy - jpy_amount
            shortfall_pnc = jpy_to_pnc(shortfall)

            embed = create_embed(
                "",
                f"最低入金PNC: `{int(MIN_INITIAL_DEPOSIT):,}`（約 ¥{int(gross_min_jpy):,}）が必要です。\n"
                f"手数料目安: 約 ¥{int(min_fee_jpy):,}。\n"
                f"合計必要額: 約 ¥{int(required_jpy):,}（不足分: 約 ¥{int(shortfall):,} ≒ {PNC_EMOJI_STR}`{int(shortfall_pnc)}`）を送金してください。",
                discord.Color.yellow()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            paypay_session.paypay.link_receive(paypay_link)
            update_user_balance(user_id, int(net_pnc))
            log_transaction(user_id=user_id, type="payin", amount=int(jpy_amount), payout=int(net_pnc))

            embed = discord.Embed(title="入金完了", color=discord.Color.green())
            embed.add_field(name="入金額", value=f"`¥{int(jpy_amount):,}` → {PNC_EMOJI_STR} `{int(total_pnc):,}`", inline=True)
            embed.add_field(name="手数料（14% or ¥10）", value=f"`¥{int(fee_jpy):,}` → {PNC_EMOJI_STR} `{int(fee_pnc):,}`", inline=True)
            embed.add_field(name="現在の残高", value=f"{PNC_EMOJI_STR}`{get_user_balance(user_id):,}`", inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)
            await send_paypay_log(user, jpy_amount, fee_jpy, net_pnc, link_info)
        except PayPayError:
            embed = create_embed("", "入金処理中にエラーが発生しました。リンクが無効か既に使用済みです。", discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)