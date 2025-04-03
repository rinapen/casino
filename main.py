import discord
from discord import app_commands
from discord.ext import tasks, commands
import config
import datetime
from datetime import timedelta
import os
import pytz
import matplotlib.pyplot as plt
from bot import bot
from utils.pnc import get_total_pnc, get_daily_profit, get_monthly_revenue
import asyncio
import commands

JST = pytz.timezone("Asia/Tokyo")

@tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=JST))  # ⏰ **毎日 0:00 JST に実行**
async def daily_report_task():
    """⏳ 自動的に毎日 0:00 JST にレポートを送信"""
    await send_daily_report()


async def send_daily_report(target_date: str = None):
    """📝 指定した日のカジノ収益レポートを送信（デフォルトは昨日）"""

    if target_date is None:
        now = datetime.datetime.now(JST)
        target_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    # **利益計算**
    daily_profit = get_daily_profit(target_date)
    total_pnc = get_total_pnc()
    monthly_revenue = get_monthly_revenue()

    # **利益率計算（PNCが0のときは0.0%）**
    profit_rate = (daily_profit / total_pnc * 100) if total_pnc > 0 else 0.0

    channel = bot.get_channel(int(config.ADMIN_CHANNEL_ID))
    if channel:
        embed = discord.Embed(
            title="💰 カジノ収益レポート",
            description=f"**{target_date} のカジノ利益状況**",
            color=discord.Color.gold()
        )
        embed.add_field(name="📈 本日の利益", value=f"`{daily_profit:,} 円`", inline=False)
        embed.add_field(name="📊 利益率", value=f"`{profit_rate:.2f}%`", inline=False)
        embed.add_field(name="📅 1ヶ月の総収益", value=f"`{monthly_revenue:,} 円`", inline=False)
        embed.add_field(name="💳 全ユーザー保有PNC", value=f"`{total_pnc:,} PNC`", inline=False)
        embed.set_footer(text="⏳ 自動送信 - カジノレポート")

        await channel.send(embed=embed)

def create_profit_graph(target_date):
    """📈 指定した日の利益グラフを作成し保存"""
    REPORTS_DIR = "reports"
    os.makedirs(REPORTS_DIR, exist_ok=True)

    dates = [(datetime.datetime.now(JST) - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)]
    profits = [get_daily_profit(date) for date in dates]

    plt.figure(figsize=(10, 5))
    plt.plot(dates, profits, marker='o', linestyle='-', color='green')
    plt.xlabel("📆 日付")
    plt.ylabel("💰 利益 (PNC)")
    plt.title(f"📊 カジノ利益推移 ({target_date})")
    plt.xticks(rotation=45)
    plt.grid()

    image_path = os.path.join(REPORTS_DIR, f"{target_date}_profit.png")
    plt.savefig(image_path, bbox_inches="tight")
    plt.close()

    return image_path


async def keep_alive():
    """🔄 ボットの接続状態を監視"""
    while True:
        await bot.wait_until_ready()
        print(f"✅ WebSocket is stable: {round(bot.latency * 1000)}ms")
        await asyncio.sleep(300)  # **5分ごとに監視**


@bot.event
async def on_ready():
    """🔵 ボット起動時にタスクを開始"""
    await bot.tree.sync()
    print(f"🟢 Logged in as {bot.user}")

    # **タスクがすでに起動していなければ開始**
    if not daily_report_task.is_running():
        daily_report_task.start()


async def main():
    """🔄 メイン関数（非同期起動）"""
    asyncio.create_task(keep_alive())  # ✅ `create_task()` を `async` 関数内で実行
    await bot.start(config.TOKEN)  # ✅ `bot.run()` を `await bot.start()` に変更

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 ボットの実行を中断しました。終了します。")