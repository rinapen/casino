import asyncio
import hashlib
import secrets
import discord

from database.db import get_user_balance, update_user_balance, save_pf_params
from utils.stake_mines import get_stake_multiplier
from utils.logs import send_casino_log, log_transaction
from utils.emojis import MINE_EMOJI, DIAMOND_EMOJI, MINE_EMOJI_TEXT, DIAMOND_EMOJI_TEXT, PNC_EMOJI_STR, WIN_EMOJI
from utils.sys import generate_server_seed, hash_server_seed, get_hmac_sha256
from utils.color import BASE_COLOR_CODE

GRID_SIZE = 5

def create_mines_embed(game, reveal_all=False, result=None, payout=None):
    grid_display = ""
    for x in range(GRID_SIZE):
        row = []
        for y in range(GRID_SIZE):
            if reveal_all:
                row.append(DIAMOND_EMOJI_TEXT if (x, y) not in game.mines else MINE_EMOJI_TEXT)
            elif (x, y) in game.revealed:
                row.append(DIAMOND_EMOJI_TEXT if (x, y) not in game.mines else MINE_EMOJI_TEXT)
            else:
                row.append("⬜")
        grid_display += " ".join(row) + "\n"

    total_tiles = GRID_SIZE * GRID_SIZE
    total_revealed = len(game.revealed)
    remaining_gems = total_tiles - game.mine_count - total_revealed

    profit = (payout if payout is not None else game.current_reward) - game.bet
    displayed_profit = max(profit, 0)

    if result == "ハズレを引いた！":
        embed_color = discord.Color.from_str("#ff3d74")  # 敗北色
    elif result == "勝ったね!":
        embed_color = discord.Color.from_str("#26ffd4")  # 勝利色
    else:
        embed_color = BASE_COLOR_CODE

    embed = discord.Embed(title="PNCマインズ", color=embed_color)
    embed.set_author(
        name=f"{game.user.name}",
        icon_url=game.user.display_avatar.url
    )
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1219916908485283880/1386292653318209647/ChatGPT_Image_2025622_19_31_53.png?ex=68592d24&is=6857dba4&hm=b8949b8e92394ebf1d2ef1f159fa408153e462c6c519eead391d8bfc52fb6740&")
    if not (result and payout is not None):
        embed.add_field(name="**Bet数**", value=f"{PNC_EMOJI_STR}`{game.bet}`", inline=False)
        embed.add_field(name="**Mines**", value=f"`{game.mine_count}`", inline=True)
        embed.add_field(name="**Gems**", value=f"`{remaining_gems}`", inline=True)
        embed.add_field(name=f"**利益 ({game.payout_multiplier:.2f}×)**", value=f"{PNC_EMOJI_STR}`{round(displayed_profit)}`", inline=False)

    if result and payout is not None:
        embed.add_field(name="**トータルPNC**", value=f"{PNC_EMOJI_STR}`{payout}`", inline=True)
        embed.add_field(name="**トータル利益**", value=f"{PNC_EMOJI_STR}`{max(payout - game.bet, 0)}`", inline=True)

    return embed

async def update_mines_board(interaction, game):
    embed = create_mines_embed(game)
    view = MinesView(game.user_id, game)

    for child in view.children:
        if isinstance(child, MinesButton):
            if (child.x, child.y) in game.revealed:
                if (child.x, child.y) in game.mines:
                    child.style = discord.ButtonStyle.secondary
                    child.label = None
                    child.emoji = MINE_EMOJI
                else:
                    child.style = discord.ButtonStyle.secondary
                    child.label = None
                    child.emoji = DIAMOND_EMOJI
                child.disabled = True
    try:
        await interaction.response.edit_message(embed=embed, view=view)
    except discord.errors.InteractionResponded:
        await interaction.message.edit(embed=embed, view=view)

async def end_mines_game(interaction, game, result, payout, edit_cashout: bool = True):
    reveal_all = result == "ハズレを引いた！"
    embed = create_mines_embed(game, reveal_all=reveal_all, result=result, payout=payout)

    # 🔐 PF情報
    embed.add_field(name="🔐Provably Fair", value=(
        f"Hash: `{game.server_seed_hash}`\n"
        f"Seed: `{game.server_seed}`\n"
        f"Client: `{game.client_seed}`\n"
        f"Nonce: `{game.nonce}`"
    ), inline=False)

    embed.add_field(name="🧭 Bombs (Mines)", value=", ".join(
        f"({x},{y})" for x, y in sorted(game.mines)
    ), inline=False)

    embed.set_footer(text="検証方法：SHA‑256(Hash確認)、HMAC＋ derive_mine_positions()で爆弾再現可")

    try:
        save_pf_params(game.user_id, game.client_seed, game.server_seed, game.nonce + 1)
    except Exception as e:
        print(f"[ERROR] failed to save PF params: {e}")


    if reveal_all:
        view = MinesView(game.user_id, game)
        for child in view.children:
            if isinstance(child, MinesButton):
                pos = (child.x, child.y)
                child.disabled = True
                if pos in game.mines:
                    child.style = discord.ButtonStyle.danger
                    child.label = None
                    child.emoji = MINE_EMOJI
                else:
                    child.style = discord.ButtonStyle.secondary
                    child.label = None
                    child.emoji = DIAMOND_EMOJI
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except discord.errors.InteractionResponded:
            await interaction.message.edit(embed=embed, view=view)

    else:
        try:
            view = MinesView(game.user_id, game)
            for child in view.children:
                pos = (child.x, child.y)
                child.disabled = True 

                if pos in game.revealed:
                    if pos in game.mines:
                        child.style = discord.ButtonStyle.secondary
                        child.label = None
                        child.emoji = MINE_EMOJI
                    else:
                        child.style = discord.ButtonStyle.secondary
                        child.label = None
                        child.emoji = DIAMOND_EMOJI
                else:
                    child.style = discord.ButtonStyle.secondary
                    child.label = "‎"
                    child.emoji = None

            if game.message_id:
                original_game_msg = await interaction.channel.fetch_message(game.message_id)
                await original_game_msg.edit(embed=embed, view=view)
        except Exception as e:
            print(f"[ERROR] Failed to disable buttons after cashout: {e}")


    if edit_cashout and result == "ハズレを引いた！" and hasattr(game, "cashout_message_id"):
        cashout_embed = discord.Embed(description="ゲームが終了しました。", color=BASE_COLOR_CODE) 
        cashout_view = discord.ui.View()
        cashout_view.add_item(CashoutButton(game.user_id, game, disabled=True))
        try:
            channel = interaction.channel
            msg = await channel.fetch_message(game.cashout_message_id)
            await msg.edit(embed=cashout_embed, view=cashout_view)
        except discord.errors.NotFound:
            print("[ERROR] Cashout message not found.")
        except Exception as e:
            print(f"[ERROR] Failed to edit cashout message: {e}")

def derive_mine_positions(hmac_hex: str, grid_size: int, mine_count: int):
    positions = list(range(grid_size * grid_size))
    selected = []
    i = 0
    pool = hmac_hex
    while len(selected) < mine_count:
        if i * 4 + 4 > len(pool):
            pool += hashlib.sha256(pool.encode()).hexdigest()
        seg = pool[i*4:(i+1)*4]
        idx = int(seg, 16) % len(positions)
        selected.append(positions.pop(idx))
        i += 1
    return {(pos // grid_size, pos % grid_size) for pos in selected}

class MinesGame:
    def __init__(self, user: discord.User, bet: int, mine_count: int, client_seed: str = None, nonce: int = 0):
        self.user = user
        self.user_id = user.id
        self.bet = bet
        self.mine_count = mine_count
        self.client_seed = client_seed or secrets.token_hex(8)
        self.nonce = nonce

        self.server_seed = generate_server_seed()
        self.server_seed_hash = hash_server_seed(self.server_seed)
        self.hmac = get_hmac_sha256(self.server_seed, self.client_seed, self.nonce)
        self.mines = derive_mine_positions(self.hmac, GRID_SIZE, mine_count)

        self.revealed = set()
        self.finished = False
        self.consecutive_wins = 0
        self.payout_multiplier = 1.0
        self.current_reward = 0
        self.cashout_message_id = None
        self.message_id = None

    def reveal(self, x, y):
        if self.finished or (x, y) in self.revealed:
            return None

        self.revealed.add((x, y))
        if (x, y) in self.mines:
            self.finished = True
            all_pos = [(i, j) for i in range(GRID_SIZE) for j in range(GRID_SIZE)]
            for i, j in all_pos:
                if (i, j) not in self.revealed:
                    self.revealed.add((i, j))
            return "lose"

        self.consecutive_wins += 1
        self.payout_multiplier = get_stake_multiplier(self.mine_count, self.consecutive_wins)
        self.current_reward = round(self.bet * self.payout_multiplier)
        return "win"

    def cashout(self):
        if self.finished:
            return None
        self.finished = True
        all_pos = [(i, j) for i in range(GRID_SIZE) for j in range(GRID_SIZE)]
        for i, j in all_pos:
            if (i, j) not in self.revealed:
                self.revealed.add((i, j))
        return round(self.current_reward)

    def get_provably_fair_info(self):
        return {
            "server_seed_hash": self.server_seed_hash,
            "server_seed": self.server_seed,
            "client_seed": self.client_seed,
            "nonce": self.nonce,
            "mine_positions": sorted(self.mines)
        }

class MinesView(discord.ui.View):
    def __init__(self, user_id, game):
        super().__init__(timeout=None) 
        self.user_id = user_id
        self.game = game

        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                self.add_item(MinesButton(user_id, game, row, col))

class MinesButton(discord.ui.Button):
    def __init__(self, user_id, game, x, y):
        super().__init__(style=discord.ButtonStyle.secondary, label="‎", row=x)
        self.user_id = user_id
        self.game = game
        self.x = x
        self.y = y
        

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ **このゲームの参加者ではありません！**", ephemeral=True)
            return

        if self.game.finished:
            await interaction.response.send_message("❌ **ゲームはすでに終了しています！**", ephemeral=True)
            return

        result = self.game.reveal(self.x, self.y)

        if result == "lose":
            payout = 0
            
            log_transaction(self.user_id, "mines", self.game.bet, payout)
            await end_mines_game(interaction, self.game, "ハズレを引いた！", payout)
        elif result == "win":
            await update_mines_board(interaction, self.game)
        else:
            await interaction.response.send_message("❌ **無効な操作です！**", ephemeral=True)

class CashoutButton(discord.ui.Button):
    def __init__(self, user_id, game, disabled=False):
        super().__init__(style=discord.ButtonStyle.success, label="出金", disabled=disabled, custom_id=f"cashout:{user_id}")
        self.user_id = user_id
        self.game = game

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("**この出金ボタンはあなたのものではありません！**", ephemeral=True)
            return

        if self.game.finished:
            await interaction.response.send_message(embed=discord.Embed(title="出金不可", description="**すでにゲームが終了しています！**", color=discord.Color.red()), ephemeral=True)
            return

        payout = self.game.cashout()
        update_user_balance(self.user_id, payout)
        log_transaction(self.user_id, "mines", self.game.bet, payout)
        await send_casino_log(
            interaction, winorlose="WIN", emoji=WIN_EMOJI, price=payout,
            description="",
            color=discord.Color.from_str("#26ffd4"),
        )
        new_balance = get_user_balance(self.user_id)

        # ✅ 非同期でまとめて実行
        async def send_ephemeral():
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"### {PNC_EMOJI_STR}`{payout}` **WIN**\n\n**現在の残高**: {PNC_EMOJI_STR}`{new_balance}`",
                    color=discord.Color.green()
                ),
                # ephemeral=True
            )

        async def edit_game_embed():
            await end_mines_game(interaction, self.game, "勝ったね!", payout, edit_cashout=False)

        async def disable_cashout_button():
            try:
                original_message = await interaction.channel.fetch_message(interaction.message.id)
                new_view = discord.ui.View()
                new_view.add_item(CashoutButton(self.user_id, self.game, disabled=True))
                await original_message.edit(view=new_view)
            except Exception as e:
                print(f"[ERROR] Failed to disable cashout button after payout: {e}")

        await asyncio.gather(
            send_ephemeral(),
            edit_game_embed(),
            disable_cashout_button()
        )