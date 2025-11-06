"""
カジノボットメインモジュール
Discord Bot のエントリーポイントと定期タスクを管理します
"""
import asyncio
import datetime
import os
import random
from datetime import timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
import pytz

from bot import bot
from database.db import payin_settings_collection 
from commands import register_all_text_commands
from commands.table_management import setup_table_commands
from config import GUILD_ID, JST
import config
from paypay_session import paypay_session
from tasks.usage_ranking import send_monthly_usage_ranking, send_or_update_ranking
from utils.account_panel import setup_account_panel
from utils.invite_panel import check_invite_usage_diff, initialize_invite_cache, setup_invite_panel
from utils.pnc import get_daily_profit, get_total_pnc, get_total_revenue

# ========================================
# 定期タスク
# ========================================

@tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=JST))
async def daily_report_task() -> None:
    """日次レポート送信タスク（毎日0時実行）"""
    await send_daily_report()


@tasks.loop(seconds=60)
async def invite_monitor_loop() -> None:
    """招待監視タスク（60秒ごと）"""
    guild = bot.get_guild(GUILD_ID)
    if guild:
        try:
            await check_invite_usage_diff(guild)
            print("✅ Invite usage diff checked")
        except Exception as e:
            print(f"❌ Error during invite diff check: {e}")


# ========================================
# レポート生成
# ========================================
async def send_daily_report(target_date: Optional[str] = None) -> None:
    """
    日次カジノレポートを送信
    
    Args:
        target_date: 対象日付（YYYY-MM-DD形式）。Noneの場合は昨日
    """
    if target_date is None:
        now = datetime.datetime.now(JST)
        target_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    daily_profit = get_daily_profit(target_date)
    total_pnc = get_total_pnc()
    monthly_revenue = get_total_revenue()

    profit_rate = (daily_profit / total_pnc * 100) if total_pnc > 0 else 0.0

    if not config.ADMIN_CHANNEL_ID:
        print("[WARN] ADMIN_CHANNEL_ID is not set")
        return
        
    channel = bot.get_channel(int(config.ADMIN_CHANNEL_ID))
    if channel:
        embed = discord.Embed(
            title="カジノ収益レポート",
            description=f"**{target_date} のカジノ利益状況**",
            color=discord.Color.gold()
        )
        embed.add_field(name="本日の利益", value=f"`{daily_profit:,} 円`", inline=False)
        embed.add_field(name="利益率", value=f"`{profit_rate:.2f}%`", inline=False)
        embed.add_field(name="総収益", value=f"`{monthly_revenue:,} 円`", inline=False)
        embed.add_field(name="全ユーザー保有PNC", value=f"`{total_pnc:,} PNC`", inline=False)
        embed.set_footer(text="自動送信 - カジノレポート")

        await channel.send(embed=embed)

        graph_path = create_monthly_profit_graph()
        file = discord.File(graph_path, filename="monthly_profit.png")
        graph_embed = discord.Embed(
            title="直近30日間のカジノ利益推移",
            color=discord.Color.blurple()
        )
        graph_embed.set_image(url="attachment://monthly_profit.png")
        await channel.send(embed=graph_embed, file=file)

def create_monthly_profit_graph() -> str:
    """
    過去30日間のカジノ利益推移グラフを作成
    
    Returns:
        str: 生成されたグラフ画像のパス
    """
    REPORTS_DIR = "reports"
    os.makedirs(REPORTS_DIR, exist_ok=True)

    font_path = "assets/font/NotoSansJP-VariableFont_wght.ttf"
    jp_font = fm.FontProperties(fname=font_path)

    today = datetime.datetime.now(JST)
    dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(29, -1, -1)]
    profits = [get_daily_profit(date) for date in dates]

    plt.figure(figsize=(12, 6))
    plt.plot(dates, profits, marker='o', linestyle='-', color='blue')

    plt.title("📊 過去30日間のカジノ収益推移", fontproperties=jp_font)
    plt.xlabel("日付", fontproperties=jp_font)
    plt.ylabel("利益（円）", fontproperties=jp_font)
    plt.xticks(rotation=45, fontproperties=jp_font)
    plt.yticks(fontproperties=jp_font)
    plt.grid(True)

    # データラベルを追加
    for i, profit in enumerate(profits):
        plt.annotate(
            f"{profit:,}",
            (dates[i], profits[i]),
            textcoords="offset points",
            xytext=(0, 8),
            ha='center',
            fontsize=8,
            fontproperties=jp_font
        )

    plt.tight_layout()
    image_path = os.path.join(REPORTS_DIR, "monthly_profit.png")
    plt.savefig(image_path, bbox_inches="tight")
    plt.close()
    
    return image_path

# ========================================
# 生存確認タスク
# ========================================
async def keep_alive() -> None:
    """
    WebSocketとPayPayセッションの生存確認
    4-7分ごとにランダムに実行
    """
    while True:
        await bot.wait_until_ready()
        print(f"✅ WebSocket is stable: {round(bot.latency * 1000)}ms")
        
        try:
            paypay_session.paypay.alive()
        except Exception as e:
            print(f"[ERROR] keep_alive error: {e}")
        
        # ランダムな間隔で実行（240-420秒）
        sleep_time = random.randint(240, 420)
        await asyncio.sleep(sleep_time)


# ========================================
# スラッシュコマンド
# ========================================
@bot.tree.command(name="換金率キャンペーン", description="換金率100%キャンペーンをON/OFFします（管理者専用）")
@app_commands.describe(mode="trueでON、falseでOFF")
async def toggle_no_fee(interaction: discord.Interaction, mode: bool) -> None:
    """換金率キャンペーンの有効/無効を切り替え"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("権限がありません。", ephemeral=True)
        return

    payin_settings_collection.update_one(
        {"_id": "conversion_rate"},
        {"$set": {"no_fee_mode": mode}},
        upsert=True
    )

    status = "有効化✅" if mode else "無効化❌"
    await interaction.response.send_message(f"換金率100%キャンペーンを{status}しました。", ephemeral=True)

# ========================================
# イベントハンドラー
# ========================================
@bot.event
async def on_ready() -> None:
    """ボット起動時の初期化処理"""
    print("[DEBUG] on_ready 実行開始")
    
    # テーブル管理コマンドをセットアップ
    await setup_table_commands(bot)
    
    # スラッシュコマンドを同期
    await bot.tree.sync()
    print(f"🟢 Logged in as {bot.user}")

    # 招待キャッシュの初期化
    for guild in bot.guilds:
        if guild.id == GUILD_ID:
            try:
                await initialize_invite_cache(guild)
                print(f"✅ Initialized invite cache for {guild.name}")
            except Exception as e:
                print(f"❌ Failed to initialize invites for {guild.name}: {e}")

    # アカウントパネルのセットアップ
    await setup_account_panel()
    # await setup_invite_panel(bot)  # 必要に応じてコメント解除

    # 定期タスクの開始
    if not daily_report_task.is_running():
        daily_report_task.start()

    if not invite_monitor_loop.is_running():
        invite_monitor_loop.start()

    if not send_monthly_usage_ranking.is_running():
        send_monthly_usage_ranking.start()

    # 初回ランキング送信
    await send_or_update_ranking()
    
    # 初回レポート送信
    try:
        await send_daily_report()
    except Exception as e:
        print(f"[ERROR] 起動時レポート送信エラー: {e}")
        
        if config.ADMIN_CHANNEL_ID:
            error_embed = discord.Embed(
                title="⚠️ レポート送信エラー",
                description=f"Bot起動時にカジノ収益レポートの送信に失敗しました。\n`{type(e).__name__}: {str(e)}`",
                color=discord.Color.red()
            )
            error_channel = bot.get_channel(int(config.ADMIN_CHANNEL_ID))
            if error_channel:
                await error_channel.send(embed=error_embed)


# ========================================
# メインエントリーポイント
# ========================================
async def main() -> None:
    """ボットのメイン処理"""
    # 生存確認タスクをバックグラウンドで実行
    asyncio.create_task(keep_alive())
    
    # テキストコマンドを登録
    await register_all_text_commands(bot)
    
    # ボットを起動
    if not config.TOKEN:
        raise ValueError("DISCORD_BOT_TOKEN が設定されていません")
    
    await bot.start(config.TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 ボットの実行を中断しました。終了します。")