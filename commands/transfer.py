import discord
import re
from database.db import get_user_balance, update_user_balance

from utils.embed import create_embed
from utils.logs import log_transaction
from utils.emojis import PNC_EMOJI_STR
from utils.embed_factory import EmbedFactory

from config import TAX_RATE, FEE_RATE

async def on_transfer_command(message: discord.Message):
    pattern = r"\$送金\s+<@!?(\d+)>\s+(\d+)"
    match = re.match(pattern, message.content)

    if not match:
        embed = create_embed("", "`$送金 @ユーザー 金額` の形式で入力してください。", discord.Color.red())
        await message.channel.send(embed=embed)
        return

    sender_id = message.author.id
    recipient_id = int(match.group(1))
    amount = int(match.group(2))

    if sender_id == recipient_id:
        embed = create_embed("", "自分自身には送金できないよw", discord.Color.red())
        await message.channel.send(embed=embed)
        return

    sender_balance = get_user_balance(sender_id)
    recipient_balance = get_user_balance(recipient_id)

    if sender_balance is None:
        embed = EmbedFactory.not_registered()
        await message.channel.send(embed=embed)
        return
    if recipient_balance is None:
        embed = create_embed("", "受取人がまだアカウントを紐付けていません。", discord.Color.red())
        await message.channel.send(embed=embed)
        return

    fee = int(amount * (TAX_RATE + FEE_RATE))
    total_deduction = amount + fee

    if sender_balance < total_deduction:
        embed = EmbedFactory.insufficient_balance(sender_balance)
        await message.channel.send(embed=embed)
        return

    update_user_balance(sender_id, -total_deduction)
    update_user_balance(recipient_id, amount)
    log_transaction(user_id=sender_id, type="transfer", amount=total_deduction, payout=amount)

    embed = discord.Embed(title="✅ 送金完了", color=discord.Color.blue())
    embed.add_field(name="送金額", value=f"{PNC_EMOJI_STR}`{amount:,}`", inline=False)
    embed.add_field(name="手数料", value=f"{PNC_EMOJI_STR}`{fee:,}`", inline=False)
    embed.add_field(name="合計引き落とし", value=f"{PNC_EMOJI_STR}`{total_deduction:,}`", inline=False)

    try:
        recipient = await message.guild.fetch_member(recipient_id)
        embed.add_field(name="受取人", value=f"{recipient.display_name} 様", inline=False)
    except:
        embed.add_field(name="受取人", value=f"<@{recipient_id}>", inline=False)

    embed.set_footer(text=f"{message.author.display_name} | 残高: {get_user_balance(sender_id):,}")
    await message.channel.send(embed=embed)

    try:
        user = await message.guild.fetch_member(recipient_id)
        await user.send(f"**{message.author.display_name}** から {PNC_EMOJI_STR}`{amount:,}` を受け取りました！\n"
                        f"残高: {PNC_EMOJI_STR}`{get_user_balance(recipient_id):,}`")
    except discord.Forbidden:
        await message.channel.send(f"⚠ 送金は完了しましたが、<@{recipient_id}> にDMを送信できませんでした。")