import discord
from discord import app_commands
from database import user_transactions_collection
from bot import bot
from config import BASE_COLOR_CODE
PAGE_SIZE = 5

@bot.tree.command(name="rireki", description="取引明細を表示")
async def rireki(interaction: discord.Interaction):
    user_id = interaction.user.id
    transactions = list(user_transactions_collection.find({"user_id": user_id}).sort("timestamp", -1))

    if not transactions:
        embed = discord.Embed(title="取引履歴", description="取引履歴がありません。", color=discord.Color.dark_gray())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    await send_transaction_history(interaction, user_id, transactions, page=0)

async def send_transaction_history(interaction, user_id, transactions, page):
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    current_transactions = transactions[start:end]

    embed = discord.Embed(title="取引履歴", color=BASE_COLOR_CODE)

    for txn in current_transactions:
        type_emoji = "📥" if txn["type"] == "deposit" else "📤" if txn["type"] == "withdraw" else "🔄"
        embed.add_field(
            name=f"{type_emoji} `{txn['type'].capitalize()}` - `{txn['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}`",
            value=f"💰 **金額**: `{txn['amount']} pnc`\n"
                  f"💸 **手数料**: `{txn['fee']} pnc`\n"
                  f"📊 **合計**: `{txn['total']} pnc`",
            inline=False
        )

    view = TransactionHistoryView(user_id, transactions, page)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class TransactionHistoryView(discord.ui.View):
    def __init__(self, user_id, transactions, page):
        super().__init__()
        self.user_id = user_id
        self.transactions = transactions
        self.page = page

        start = page * PAGE_SIZE
        end = start + PAGE_SIZE

        if start > 0:
            self.add_item(PreviousPageButton(self.user_id, self.transactions, self.page))
        if end < len(transactions):
            self.add_item(NextPageButton(self.user_id, self.transactions, self.page))

class PreviousPageButton(discord.ui.Button):
    def __init__(self, user_id, transactions, page):
        super().__init__(label="◀️ 前へ", style=discord.ButtonStyle.secondary, custom_id=f"prev_{page}")
        self.user_id = user_id
        self.transactions = transactions
        self.page = page

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("この履歴を操作する権限がありません。", ephemeral=True)
            return

        await send_transaction_history(interaction, self.user_id, self.transactions, self.page - 1)

class NextPageButton(discord.ui.Button):
    def __init__(self, user_id, transactions, page):
        super().__init__(label="次へ ▶️", style=discord.ButtonStyle.secondary, custom_id=f"next_{page}")
        self.user_id = user_id
        self.transactions = transactions
        self.page = page

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("この履歴を操作する権限がありません。", ephemeral=True)
            return

        await send_transaction_history(interaction, self.user_id, self.transactions, self.page + 1)