import discord
import random
from discord import app_commands
from bot import bot
from database.db import get_user_balance, update_user_balance, get_user_streaks, update_user_streak
from utils.embed import create_embed
from utils.logs import send_casino_log
from utils.stats import log_transaction, get_user_net_profit

from config import WIN_EMOJI, LOSE_EMOJI, DRAW_EMOJI, CARD_EMOJIS

BASE_COLOR_CODE = 0x2b2d31
VALID_BETS = [100, 500, 1000]
SUITS = ["S", "C", "D", "H"]

CARD_VALUES = {str(i): i for i in range(2, 11)}
CARD_VALUES.update({"J": 10, "Q": 10, "K": 10, "A": 11})

games = {}

RESULT_TEXTS = {
    "win": "勝ちました！（奇跡的）",
    "lose": "負けました...",
    "draw": "引き分け（カジノの勝ち）",
    "bust": "バーストで死亡"
}

def draw_card():
    """ランダムなカードを引く"""
    rank = random.choice(list(CARD_VALUES.keys()))
    suit = random.choice(SUITS)
    value = CARD_VALUES[rank]

    if rank == "A":
        emoji = CARD_EMOJIS[suit][0]
    elif rank.isdigit():
        emoji = CARD_EMOJIS[suit][int(rank) - 1]
    else:
        emoji_index = {"J": 10, "Q": 11, "K": 12}[rank]
        emoji = CARD_EMOJIS[suit][emoji_index]

    return (emoji, rank, suit, value)

def calculate_hand_value(hand):
    """手札の合計値を計算"""
    value = sum(card[3] for card in hand)
    aces = sum(1 for card in hand if card[1] == "A")

    while value > 21 and aces:
        value -= 10
        aces -= 1

    return value

class BlackjackGame:
    def __init__(self, user_id, bet, win_streak):
        self.user_id = user_id
        self.bet = bet
        self.win_streak = win_streak
        self.player_hand = [draw_card(), draw_card()]
        self.dealer_hand = [draw_card(), draw_card()]
        self.finished = False

        try:
            profit = get_user_net_profit(user_id, "blackjack", days=7)
        except:
            profit = 0

        self.bias = 0
        if profit > 3000:
            self.bias = -0.15  # 勝ちすぎてる → 勝率下げる
        elif profit < -2000:
            self.bias = +0.15  # 負けすぎてる → 勝率上げる


    def hit(self):
        """プレイヤーがヒットする（バースト確率を大幅調整）"""
        if self.finished:
            return None
        
        player_score = calculate_hand_value(self.player_hand)
        
        # **バースト確率の調整**
        bust_chance = 0.1 * (self.bet // 100) + (self.win_streak * 0.1)

        if player_score >= 14:
            bust_chance += 0.3
        if player_score >= 17:
            bust_chance += 0.5
        if player_score >= 19:
            bust_chance += 0.7  

        # **バースト発生**
        if random.random() < bust_chance:
            self.player_hand.append(draw_card())
            self.player_hand.append(draw_card())  # 強制2枚ドロー
        else:
            self.player_hand.append(draw_card())

        if calculate_hand_value(self.player_hand) > 21:
            self.finished = True  
            return "bust"

        return self.player_hand

    def dealer_turn(self):
        """ディーラーのターン（19-21で止まる確率を大幅UP）"""
        player_score = calculate_hand_value(self.player_hand)
        dealer_score = calculate_hand_value(self.dealer_hand)

        while dealer_score < 19:
            if dealer_score >= 17 and random.random() < 0.9:
                break  # 90%の確率でスタンド
            if dealer_score >= 19 and dealer_score <= 21:
                break  # 19-21なら確定でスタンド

            self.dealer_hand.append(draw_card())
            dealer_score = calculate_hand_value(self.dealer_hand)

        # **プレイヤーが21の時、40%の確率でディーラーも21**
        if player_score == 21 and random.random() < 0.4:
            while dealer_score < 21:
                self.dealer_hand.append(draw_card())
                dealer_score = calculate_hand_value(self.dealer_hand)

    def get_result(self):
        """勝敗判定（プレイヤーがほぼ負ける）"""
        player_score = calculate_hand_value(self.player_hand)
        dealer_score = calculate_hand_value(self.dealer_hand)

        print(f"DEBUG: プレイヤーの手札 {self.player_hand} （合計: {player_score}）")
        print(f"DEBUG: ディーラーの手札 {self.dealer_hand} （合計: {dealer_score}）")

        if player_score > 21:
            return "bust"
        if dealer_score > 21:
            return "win"

        if player_score == 21 and dealer_score == 21:
            return "draw"  
        if player_score == 21:
            return "win" if random.random() < 0.25 else "draw"  # 25%勝ち、75%引き分け
        if dealer_score == 21:
            return "lose"

        if player_score > dealer_score:
            return "win" if random.random() < 0.15 else "lose"  # 15%勝ち、85%負け
        if player_score == dealer_score:
            return "draw"
        return "lose"

@bot.tree.command(name="blackjack", description="ブラックジャックを開始")
@app_commands.describe(amount="ベット額")
@app_commands.choices(amount=[app_commands.Choice(name=f"{b} PNC", value=b) for b in VALID_BETS])
async def blackjack(interaction: discord.Interaction, amount: int):
    user_id = interaction.user.id
    balance = get_user_balance(user_id)
    if balance < amount:
        embed = create_embed("❌ 残高不足", f"現在の残高: `{balance:,} PNC`\nベット額を減らしてください。", discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    win_streak, lose_streak = get_user_streaks(user_id, "blackjack")
    games[user_id] = BlackjackGame(user_id, amount, win_streak)
    game = games[user_id]

    embed = create_blackjack_embed(game, False, BASE_COLOR_CODE)
    await interaction.response.send_message(embed=embed, view=BlackjackView(user_id))

def create_blackjack_embed(game, reveal_dealer, color, result=None, payout=None, balance=None):
    """ブラックジャックの手札をEmbedで表示"""
    player_hand = " ".join(f"{card[0]}" for card in game.player_hand)
    dealer_hand = " ".join(f"{card[0]}" for card in game.dealer_hand) if reveal_dealer else f"{game.dealer_hand[0][0]} <:ura:1349085492448071700>"
    dealer_value = calculate_hand_value(game.dealer_hand) if reveal_dealer else "??"

    embed = discord.Embed(title="ブラックジャック", color=color)
    embed.add_field(name="**ベット額**", value=f"`{game.bet} PNC`", inline=False)
    embed.add_field(name="**プレイヤーの手札**", value=f"{player_hand} （合計: `{calculate_hand_value(game.player_hand)}`）", inline=False)
    embed.add_field(name="**ディーラーの手札**", value=f"{dealer_hand} （合計: `{dealer_value}`）", inline=False)

    if result:
        embed.add_field(name="**結果**", value=f"`{RESULT_TEXTS[result]}`", inline=False)
        if payout is not None:
            if payout > 0:
                embed.add_field(name="✅ **獲得**", value=f"`{payout} PNC`", inline=False)
            elif payout < 0:
                embed.add_field(name="❌ **損失**", value=f"`{-payout} PNC`", inline=False)

    if balance is not None:
        embed.set_footer(text=f"現在の残高: {balance} PNC")

    return embed

class BlackjackView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id

    @discord.ui.button(label="1枚引く", style=discord.ButtonStyle.green)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        user_id = interaction.user.id
        game = games.get(user_id)

        # **不正防止**
        if game is None or game.user_id != user_id:
            await interaction.followup.send("❌ **このゲームの参加者ではありません。**", ephemeral=True)
            return

        print(f"DEBUG: {user_id} がヒットボタンを押しました")

        result = game.hit()

        # **バースト処理**
        if result == "bust":
            payout = -game.bet
            emoji = LOSE_EMOJI
            color = discord.Color.red()
            await end_blackjack_game(interaction, game, "bust", payout, color, emoji)
            return

        # **手札が21になったら自動的に判定**
        player_score = calculate_hand_value(game.player_hand)

        if player_score == 21:
            game.finished = True
            game.dealer_turn()
            dealer_score = calculate_hand_value(game.dealer_hand)

            # **ディーラーも21なら 70% の確率で引き分け**
            if dealer_score == 21:
                result = "draw" if random.random() < 0.7 else "lose"
            elif dealer_score >= 19:
                result = "lose"  # **ディーラーが 19 以上なら負け**
            else:
                result = "win"

            # **支払い処理**
            if result == "draw":
                payout = 0
                emoji = DRAW_EMOJI
                color = discord.Color.light_gray()
            elif result == "win":
                payout = game.bet * 2
                update_user_balance(user_id, payout)
                emoji = WIN_EMOJI
                color = discord.Color.green()
            else:
                payout = -game.bet
                update_user_balance(user_id, payout)
                emoji = LOSE_EMOJI
                color = discord.Color.red()

            await end_blackjack_game(interaction, game, result, payout, color, emoji)
        else:
            print(f"DEBUG: {user_id} の新しい手札 {game.player_hand}")  
            await interaction.message.edit(embed=create_blackjack_embed(game, False, BASE_COLOR_CODE))


    @discord.ui.button(label="決定", style=discord.ButtonStyle.red)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        user_id = interaction.user.id
        game = games.get(user_id)

        # **不正防止：他のユーザーがボタンを押せないようにする**
        if game is None or game.user_id != user_id:
            await interaction.followup.send("❌ **このゲームの参加者ではありません。**", ephemeral=True)
            return

        game.dealer_turn()
        game.finished = True
        result = game.get_result()

        if result == "draw":
            payout = 0
            emoji = DRAW_EMOJI
            color = discord.Color.light_gray()
        elif result == "win":
            payout = game.bet * 2
            update_user_balance(user_id, payout)
            emoji = WIN_EMOJI
            color = discord.Color.green()
        else:
            payout = -game.bet
            update_user_balance(user_id, payout)
            emoji = LOSE_EMOJI
            color = discord.Color.red()

        await end_blackjack_game(interaction, game, result, payout, color, emoji)

async def end_blackjack_game(interaction, game, result, payout, color, emoji):
    user_id = game.user_id

    if result == "win":
        update_user_streak(user_id, "blackjack", True)
    elif result in ["lose", "bust"]:
        update_user_streak(user_id, "blackjack", False)

    if result == "win":
        log_transaction(user_id, "blackjack", game.bet, payout)
    elif result == "draw":
        log_transaction(user_id, "blackjack", game.bet, game.bet)
    else:
        log_transaction(user_id, "blackjack", game.bet, 0)

    balance = get_user_balance(user_id)
    await send_casino_log(interaction, emoji, abs(payout), "", color)

    await interaction.message.edit(
        embed=create_blackjack_embed(game, True, color, result=result, payout=payout, balance=balance),
        view=None
    )