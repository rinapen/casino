import discord
from discord.errors import NotFound

from bot import bot
import config
from database.db import get_account_panel_message_id, save_account_panel_message_id

from commands.account import AccountView

async def setup_account_panel():
    try:
        channel = await bot.fetch_channel(int(config.ACCOUNT_CHANNEL_ID))
        if not channel:
            print("[ERROR] チャンネルが取得できませんでした。")
            return

        old_id = await get_account_panel_message_id()
        if old_id:
            try:
                old_msg = await channel.fetch_message(old_id)
                await old_msg.delete()
                print(f"[LOG] 前のアカウントパネルを削除しました: {old_id}")
            except NotFound:
                print(f"[INFO] 削除対象のメッセージが存在しませんでした（ID: {old_id}）")
            except Exception as e:
                print(f"[WARN] アカウントパネル削除失敗: {e}")
        else:
            print("[INFO] アカウントパネルは初回送信です")

        embed = discord.Embed(
            description="### 以下のボタンから登録、入金を行えます。",
            color=discord.Color.blurple()
        )
        embed.add_field(name="登録", value="初めての方は、こちらからアカウントを紐付けてください。", inline=False)
        embed.add_field(name="入金", value="紐付け済みの方は、こちらから入金してください。", inline=False)

        new_msg = await channel.send(embed=embed, view=AccountView())
        await save_account_panel_message_id(new_msg.id)
        print(f"[LOG] 新しいアカウントパネルを送信しました: {new_msg.id}")
    except Exception as e:
        print(f"[ERROR] アカウントパネルの設置に失敗しました: {e}")