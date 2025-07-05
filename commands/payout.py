import re
import discord
from decimal import Decimal, ROUND_DOWN

from database.db import get_user_balance, update_user_balance, users_collection
from paypay_session import paypay_session
from bot import bot

from utils.embed import create_embed
from utils.emojis import PNC_EMOJI_STR
from utils.logs import log_transaction
from utils.embed_factory import EmbedFactory

from config import PAYOUT_DISABLED, PAYOUT_LOG_CHANNEL_ID

async def on_payout_command(message: discord.Message):
    if PAYOUT_DISABLED:
        embed = create_embed("⚠️ 出金一時停止中", "現在、出金機能は一時的に利用できません。", discord.Color.red())
        return await message.reply(embed=embed, mention_author=False)

    match = re.match(r"^\$出金\s+(\d+)$", message.content)
    if not match:
        embed = create_embed("", "使い方: `$出金 <金額>`", discord.Color.red())
        return await message.reply(embed=embed, mention_author=False)

    amount = int(match.group(1))
    user_id = message.author.id
    sender = users_collection.find_one({"user_id": user_id})
    if not sender or "sender_external_id" not in sender:
        embed = EmbedFactory.not_registered()
        return await message.reply(embed=embed, mention_author=False)

    if amount < 100:
        embed = create_embed("", "⚠️ 最低出金額は**100円**です。", discord.Color.yellow())
        return await message.reply(embed=embed, mention_author=False)

    amount_jpy = Decimal(amount)
    amount_pnc = int(amount_jpy * Decimal(10))  # 1円＝10PNC
    user_balance = get_user_balance(user_id)

    if user_balance is None or user_balance < amount_pnc:
        embed = EmbedFactory.insufficient_balance(user_balance)
        return await message.reply(embed=embed, mention_author=False)

    fee_pnc = int(max(Decimal(amount_pnc) * Decimal("0.18"), Decimal(10)).quantize(Decimal("1"), rounding=ROUND_DOWN))
    total_pnc = amount_pnc + fee_pnc

    if user_balance < total_pnc:
        embed = create_embed("", f"❌ 手数料込みで {PNC_EMOJI_STR}`{total_pnc:,}（＝¥{total_pnc//10:,}）` が必要です。", discord.Color.red())
        return await message.reply(embed=embed, mention_author=False)

    try:
        link_info = paypay_session.paypay.create_link(int(amount))
        link_url = link_info.link
    except Exception as e:
        embed = create_embed("❌ エラー", "出金リンクの生成に失敗しました。", discord.Color.red())
        return await message.reply(embed=embed, mention_author=False)

    update_user_balance(user_id, -int(total_pnc))
    log_transaction(user_id=user_id, type="payout", amount=amount_jpy, payout=amount_pnc)

    dm_embed = discord.Embed(title="出金リンクが生成されました", description="以下のリンクからPayPayで受け取りができます。", color=discord.Color.green())
    dm_embed.add_field(name="受け取りリンク", value=f"[受け取りはこちら]({link_url})", inline=False)
    dm_embed.set_footer(text="※リンクの有効期限に注意してください")

    embed = discord.Embed(title="✅ 出金完了", color=discord.Color.green())
    embed.add_field(name="出金額（円/PNC）", value=f"`¥{amount:,}` → {PNC_EMOJI_STR}`{amount_pnc:,}`", inline=False)
    embed.add_field(name="手数料", value=f"{PNC_EMOJI_STR}`{fee_pnc:,}`（＝¥{fee_pnc//10:,}）", inline=False)
    embed.add_field(name="合計引き落とし", value=f"{PNC_EMOJI_STR}`{total_pnc:,}`（＝¥{total_pnc//10:,}）", inline=False)
    embed.add_field(name="現在の残高", value=f"{PNC_EMOJI_STR}`{get_user_balance(user_id):,}`", inline=False)
    embed.set_footer(text="※PNCは内部で小数扱い可ですが、出金は整数PNC単位でのみ可能です")
    await message.reply(embed=embed, mention_author=False)

    try:
        await message.author.send(embed=dm_embed)
    except discord.Forbidden:
        fallback_embed = discord.Embed(
            title="出金リンク",
            description=f"DMが無効なため、ここで出金リンクを送ります。\n[受け取りはこちら]({link_url})",
            color=discord.Color.orange()
        )
        await message.reply(embed=fallback_embed, mention_author=True)

    log_embed = discord.Embed(title="出金履歴", color=discord.Color.green())
    log_embed.set_author(name=message.author.name, icon_url=message.author.display_avatar.url)
    log_embed.add_field(name="円→PNC", value=f"`¥{amount:,}` → {PNC_EMOJI_STR}`{amount_pnc:,}`", inline=True)
    log_embed.add_field(name="手数料", value=f"{PNC_EMOJI_STR}`{fee_pnc:,}`", inline=True)
    log_embed.add_field(name="合計PNC引落とし", value=f"{PNC_EMOJI_STR}`{total_pnc:,}`", inline=False)
    log_embed.add_field(name="決済番号", value=f"`{link_info.order_id}`", inline=False)
    log_embed.set_footer(text=f"残高: {get_user_balance(user_id):,} PNC")

    try:
        channel = await bot.fetch_channel(int(PAYOUT_LOG_CHANNEL_ID))
        await channel.send(embed=log_embed)
    except Exception as e:
        print(f"[ERROR] ログチャンネル送信失敗: {e}")