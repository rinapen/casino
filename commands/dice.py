import discord
from discord import File
import random
import asyncio

from database.db import get_user_balance, update_user_balance
from utils.embed import create_embed
from utils.logs import send_casino_log
from utils.color import BASE_COLOR_CODE
from utils.emojis import PNC_EMOJI_STR, WIN_EMOJI

from ui.game.dice import ongoing_games
from ui.game.dice import ContinueButton

from config import DICE_FOLDER

async def on_dice_command(message):
    try:
        args = message.content.strip().split()
        if len(args) != 2 or not args[1].isdigit():
            embed = create_embed("", "`$ダイス 金額`の形式で入力してください。", discord.Color.red())
            embed.set_author(
                name=f"{message.author.name}",
                icon_url=message.author.display_avatar.url
            )
        
            return await message.channel.send(embed=embed)

        bet_amount = int(args[1])
        if bet_amount < 50:
            embed = create_embed("", "ベット額は50以上にしてください。", discord.Color.red())
            embed.set_author(
                name=f"{message.author.name}",
                icon_url=message.author.display_avatar.url
            )
            return await message.channel.send(embed=embed)

        user_id = message.author.id
        balance = get_user_balance(user_id)
        if balance is None:
            embed = create_embed("", "あなたはアカウントを紐づけていません。<#1379480186164088905>のパネルから登録してください。", discord.Color.red())
            await message.channel.send(embed=embed)
            return
        if bet_amount > balance:
            embed = create_embed("", f"残高不足。\n### {PNC_EMOJI_STR}`{balance:,}`", discord.Color.red())
            embed.set_author(
                name=f"{message.author.name}",
                icon_url=message.author.display_avatar.url
            )
            return await message.channel.send(embed=embed)
        update_user_balance(user_id, -bet_amount)

        def roll():
            return random.randint(1, 6), random.randint(1, 6)

        die1, die2 = roll()
        total = die1 + die2

        gif_path1 = f"{DICE_FOLDER}/gif/{die1}.gif"
        gif_path2 = f"{DICE_FOLDER}/gif/{die2}.gif"
        files = [File(gif_path1, filename="dice1.gif"), File(gif_path2, filename="dice2.gif")]
        embed = create_embed("PNCダイス", f"{PNC_EMOJI_STR}`{bet_amount}`を賭けてサイコロを振っています...", BASE_COLOR_CODE)
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1219916908485283880/1389815902278647818/ChatGPT_Image_202572_12_51_52.png?ex=6865fe6c&is=6864acec&hm=1532507b0941122a27dbc8859aa83321cad484328bd9f310d43c3b7ed63a2fcc&")
        embed.set_author(
            name=f"{message.author.name}",
            icon_url=message.author.display_avatar.url
        )
        rolling_msg = await message.channel.send(
            embed=embed,
            files=files
        )

        await asyncio.sleep(1.5)

        result_path1 = f"{DICE_FOLDER}/png/{die1}.png"
        result_path2 = f"{DICE_FOLDER}/png/{die2}.png"
        files = [File(result_path1, filename="die1.png"), File(result_path2, filename="die2.png")]

        result_embed = create_embed(
            title="PNCダイス結果",
            description=f"# {die1} + {die2} = **{total}**",
            color=discord.Color.from_str("#26ffd4")
        )
        result_embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1219916908485283880/1389815902278647818/ChatGPT_Image_202572_12_51_52.png?ex=6865fe6c&is=6864acec&hm=1532507b0941122a27dbc8859aa83321cad484328bd9f310d43c3b7ed63a2fcc&")
        result_embed.set_author(
                name=f"{message.author.name}",
                icon_url=message.author.display_avatar.url
            )
        await rolling_msg.edit(embed=result_embed, attachments=files)

        if total in [7, 11]:
            winnings = bet_amount * 2
            update_user_balance(user_id, winnings)
            result_text = f"### {PNC_EMOJI_STR}`{winnings}` **WIN**"
            summary_embed = create_embed("", result_text, BASE_COLOR_CODE)
            await message.channel.send(embed=summary_embed)

            class FakeInteraction:
                user = message.author

            await send_casino_log(
                interaction=FakeInteraction(),
                winorlose="WIN",
                emoji=WIN_EMOJI,
                price=winnings - bet_amount,
                description=f"",
                color=discord.Color.from_str("#26ffd4")
            )

        elif total in [2, 3, 12]:
            result_text = f"### クラップス！\n# {PNC_EMOJI_STR}`{bet_amount}` **LOSE**"
            summary_embed = create_embed("", result_text, BASE_COLOR_CODE)
            await message.channel.send(embed=summary_embed)

        else:
            result_text = f"### ポイント: {total}\n# {PNC_EMOJI_STR}`{bet_amount}` 継続可能！"
            summary_embed = create_embed("", result_text, BASE_COLOR_CODE)
            await message.channel.send(embed=summary_embed, view=ContinueButton(user_id, bet_amount, total))
            ongoing_games[user_id] = {"bet": bet_amount, "point": total}

    except Exception as e:
        print("Dice error:", e)
        import traceback
        traceback.print_exc()
        error_embed = create_embed("エラー", "⚠️ ゲーム中にエラーが発生しました。", discord.Color.red())
        await message.channel.send(embed=error_embed)