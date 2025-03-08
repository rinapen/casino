import config
from bot import bot
import commands 
import asyncio

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

bot.run(config.TOKEN)