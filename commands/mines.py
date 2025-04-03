import discord
import random
from discord import app_commands
from bot import bot
from database.db import get_user_balance, update_user_balance
from utils.logs import b_send_casino_log
from config import WIN_EMOJI, LOSE_EMOJI

BASE_COLOR_CODE = 0x2b2d31
VALID_BETS = [100, 500, 1000]
GRID_SIZE = 5
MINE_OPTIONS = [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]  # 最大15個

games = {}

class MinesGame:
    def __init__(self, user_id, bet, mine_count):
        self.user_id = user_id
        self.bet = bet
        self.mine_count = mine_count
        self.grid = [["⬜" for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.mines = set(random.sample([(x, y) for x in range(GRID_SIZE) for y in range(GRID_SIZE)], self.mine_count))
        self.revealed = set()
        self.finished = False

        self.base_reward = bet / (5 + self.mine_count / 5)
        self.current_reward = 0  
        self.payout_multiplier = 1.0
        self.consecutive_wins = 0

    def reveal(self, x, y):
        """マスを開ける処理"""
        if self.finished or (x, y) in self.revealed:
            return None
        self.revealed.add((x, y))

        if (x, y) in self.mines:
            self.grid[x][y] = "💣"
            self.finished = True
            return "lose"

        self.grid[x][y] = "💎"
        self.consecutive_wins += 1

        self.payout_multiplier = 1.0 + (0.01 + self.mine_count * 0.008) * self.consecutive_wins  
        self.current_reward = self.base_reward * self.payout_multiplier * self.consecutive_wins

        return "win"


    def cashout(self):
        """キャッシュアウト処理"""
        if self.finished:
            return None
        self.finished = True
        return round(self.current_reward)


def create_mines_embed(game, reveal_all=False, result=None, payout=None):
    """ゲームの状況を表示"""
    grid_display = ""
    for x in range(GRID_SIZE):
        row = []
        for y in range(GRID_SIZE):
            if (x, y) in game.revealed:
                row.append("💎" if (x, y) not in game.mines else "💣")
            elif reveal_all:
                row.append("💎" if (x, y) not in game.mines else "💣")
            else:
                row.append("⬜")
        grid_display += " ".join(row) + "\n"

    embed = discord.Embed(title="💣 マインズ - Mines", color=BASE_COLOR_CODE)
    embed.add_field(name="**ゲーム盤**", value=f"```\n{grid_display}\n```", inline=False)
    embed.add_field(name="**現在の倍率**", value=f"`x{game.payout_multiplier:.2f}`", inline=True)
    embed.add_field(name="💰 **現在の獲得額**", value=f"`{round(game.current_reward)} PNC`", inline=False)
    embed.add_field(name="**地雷の数**", value=f"`{game.mine_count}個`", inline=True)

    if result:
        embed.add_field(name="**結果**", value=f"`{result}`", inline=False)
        if payout is not None:
            embed.add_field(name="💰 **最終獲得PNC**", value=f"`{payout} PNC`", inline=False)

    return embed

class MinesView(discord.ui.View):
    """5×5のボタンを5つのRowに分けてViewに追加"""
    def __init__(self, user_id, game):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.game = game

        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                self.add_item(MinesButton(user_id, game, row, col))

class MinesButton(discord.ui.Button):
    def __init__(self, user_id, game, x, y):
        super().__init__(style=discord.ButtonStyle.secondary, label="⬜", row=x)
        self.user_id = user_id
        self.game = game
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        if user_id != self.user_id:
            await interaction.response.send_message("❌ **このゲームの参加者ではありません！**", ephemeral=True)
            return

        if self.game.finished:
            await interaction.response.send_message("❌ **ゲームはすでに終了しています！**", ephemeral=True)
            return

        result = self.game.reveal(self.x, self.y)

        if result == "lose":
            payout = 0
            # update_user_balance(user_id, -self.game.bet)
            await b_send_casino_log(interaction, self.game.bet, payout, "")

            await end_mines_game(interaction, self.game, "💥 ハズレを引いた！", payout)
        else:
            await update_mines_board(interaction, self.game)

class CashoutButton(discord.ui.Button):
    """出金ボタン"""
    def __init__(self, user_id, game, disabled=False):
        super().__init__(style=discord.ButtonStyle.success, label="💰 出金", disabled=disabled)
        self.user_id = user_id
        self.game = game

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id

        if self.game.finished:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ 出金不可",
                    description="**すでにゲームが終了しています！**",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return
        
        payout = self.game.cashout()
        update_user_balance(user_id, payout)  # **獲得額のみ加算**
        new_balance = get_user_balance(user_id)  # **最新の残高を取得**

        await b_send_casino_log(interaction, self.game.bet, payout, "")
        # **出金成功メッセージ**
        await interaction.response.send_message(
            embed=discord.Embed(
                title="✅ 出金成功！",
                description=f"**{payout} PNC を出金しました！**\n\n💰 **現在の残高**: `{new_balance} PNC`",
                color=discord.Color.green()
            )
        )

        await end_mines_game(interaction, self.game, "✅ 出金成功！", payout)

async def update_mines_board(interaction, game):
    """ゲーム盤面を更新"""
    embed = create_mines_embed(game)
    view = MinesView(game.user_id, game)

    for child in view.children:
        if isinstance(child, MinesButton):
            if (child.x, child.y) in game.revealed:
                if (child.x, child.y) in game.mines:
                    child.style = discord.ButtonStyle.danger
                    child.label = "💣"
                else:
                    child.style = discord.ButtonStyle.success
                    child.label = "💎"
                child.disabled = True

    try:
        await interaction.response.edit_message(embed=embed, view=view)
    except discord.errors.InteractionResponded:
        await interaction.message.edit(embed=embed, view=view)

async def end_mines_game(interaction, game, result, payout):
    """ゲーム終了処理（ボタンを無効化し、答え合わせ）"""
    embed = create_mines_embed(game, reveal_all=True, result=result, payout=payout)
    view = MinesView(game.user_id, game)

    for child in view.children:
        if isinstance(child, MinesButton):
            child.disabled = True
            if (child.x, child.y) in game.mines:
                child.style = discord.ButtonStyle.danger 
                child.label = "💣"
            elif (child.x, child.y) in game.revealed:
                child.style = discord.ButtonStyle.success
                child.label = "💎"
            else:
                child.style = discord.ButtonStyle.primary 
                child.label = "💎"

    try:
        await interaction.response.edit_message(embed=embed, view=view)
    except discord.errors.InteractionResponded:
        await interaction.message.edit(embed=embed, view=view)

    if hasattr(game, "cashout_message_id"):
        cashout_embed = discord.Embed(
            title="💰 PNC 出金",
            description="ゲームが終了しました。",
            color=discord.Color.red() if game.finished else discord.Color.gold()
        )

        cashout_view = discord.ui.View()
        cashout_view.add_item(CashoutButton(game.user_id, game, disabled=True))

        try:
            await interaction.followup.edit_message(game.cashout_message_id, embed=cashout_embed, view=cashout_view)
        except discord.errors.NotFound:
            pass

@bot.tree.command(name="mines", description="💣 マインズをプレイ！")
@app_commands.describe(amount="ベット額", mines="地雷の数（選択肢から選択）")
@app_commands.choices(
    amount=[app_commands.Choice(name=f"{b} PNC", value=b) for b in VALID_BETS],
    mines=[app_commands.Choice(name=f"{m}個", value=m) for m in MINE_OPTIONS]
)
async def mines(interaction: discord.Interaction, amount: int, mines: int):
    """マインズのゲームを開始"""
    user_id = interaction.user.id
    balance = get_user_balance(user_id)

    if balance < amount:
        await interaction.response.send_message("❌ **残高不足！**", ephemeral=True)
        return

    update_user_balance(user_id, -amount)

    games[user_id] = MinesGame(user_id, amount, mines)
    game = games[user_id]

    embed = create_mines_embed(game)
    view = MinesView(user_id, game)

    await interaction.response.send_message(embed=embed, view=view)

    cashout_embed = discord.Embed(
        title="💰 PNC 出金",
        description="現在のPNCを引き出す場合はボタンを押してください。",
        color=discord.Color.gold()
    )

    cashout_view = discord.ui.View()
    cashout_view.add_item(CashoutButton(user_id, game, disabled=False))

    cashout_message = await interaction.followup.send(embed=cashout_embed, view=cashout_view)
    game.cashout_message_id = cashout_message.id  