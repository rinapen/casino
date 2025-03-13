import discord
import config
import datetime
import os
import pytz
import matplotlib.pyplot as plt
from discord.ext import tasks
from bot import bot
from database.db import user_transactions_collection, users_collection
from utils.pnc import get_total_pnc, get_daily_profit, get_monthly_revenue
import commands

JST = pytz.timezone("Asia/Tokyo")

async def send_daily_report():
    """Send the daily revenue report to the admin channel at 00:00 JST"""

    now = datetime.datetime.now(JST)
    today = now.strftime("%Y-%m-%d")

    daily_profit = get_daily_profit(today)
    total_pnc = get_total_pnc()
    monthly_revenue = get_monthly_revenue()

    image_path = create_profit_graph(today)

    channel = bot.get_channel(int(config.ADMIN_CHANNEL_ID))
    if channel:
        embed = discord.Embed(
            title="本日のカジノレポート",
            description=f"**{today}** のカジノ収益レポート",
            color=discord.Color.gold()
        )
        embed.add_field(name="本日の利益", value=f"`{daily_profit:,} PNC`", inline=False)
        embed.add_field(name="1ヶ月の総収益", value=f"`{monthly_revenue:,} PNC`", inline=False)
        embed.add_field(name="全ユーザー保有PNC", value=f"`{total_pnc:,} PNC`", inline=False)
        embed.set_footer(text="自動送信 - 日次カジノレポート")

        await channel.send(embed=embed)

        await channel.send(file=discord.File(image_path))

@tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=JST))
async def daily_report_task():
    """Automatically sends the daily casino report at 00:00 JST"""
    await send_daily_report()

def get_daily_profit(date):
    """Calculate net profit for a given date (income - expenses)"""
    transactions = user_transactions_collection.find({"timestamp": {"$regex": f"^{date}"}})

    total_income = sum(txn["amount"] for txn in transactions if txn["type"] == "income")
    total_expense = sum(txn["amount"] for txn in transactions if txn["type"] == "expense")

    return total_income - total_expense

def get_total_pnc():
    """Retrieve the total PNC balance across all users"""
    total = list(users_collection.aggregate([
        {"$group": {"_id": None, "total_pnc": {"$sum": "$balance"}}}
    ]))

    return total[0]["total_pnc"] if total else 0

def create_profit_graph(today):
    """Generate and save a profit graph for the past 30 days, organized in a daily folder."""
    REPORTS_DIR = "reports"
    daily_report_dir = os.path.join(REPORTS_DIR, today)
    os.makedirs(daily_report_dir, exist_ok=True)

    dates = [(datetime.datetime.now(JST) - datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)]
    profits = [get_daily_profit(date) for date in dates]

    plt.figure(figsize=(10, 5))
    plt.plot(dates, profits, marker='o', linestyle='-', color='green')
    plt.xlabel("Date")
    plt.ylabel("Profit (pnc)")
    plt.title(f"Casino Profit Trends ({today})") 
    plt.xticks(rotation=45)
    plt.grid()

    image_path = os.path.join(daily_report_dir, "daily_profit.png")
    plt.savefig(image_path, bbox_inches="tight")
    plt.close()

    return image_path

@bot.event
async def on_ready():
    """Start daily report tasks when bot is online"""
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

    if not daily_report_task.is_running():
        daily_report_task.start()

bot.run(config.TOKEN)