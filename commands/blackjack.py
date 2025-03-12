import discord
import random
from discord import app_commands
from bot import bot
from database import get_user_balance, update_user_balance
from utils import create_embed, send_casino_log
from config import WIN_EMOJI, LOSE_EMOJI, DRAW_EMOJI

BASE_COLOR_CODE = 0x2b2d31
VALID_BETS = [50, 100, 200, 500, 1000]
SUITS = ["S", "C", "D", "H"]

CARD_EMOJIS = {
    "S": ["<:s1:1348291843904901200>", "<:s2:1348291845561647196>", "<:s3:1348291847742689331>", "<:s4:1348291849332195358>",
          "<:s5:1348291851014373456>", "<:s6:1348291852788437073>", "<:s7:1348291859952304140>", "<:s8:1348291861521109122>",
          "<:s9:1348291863827714171>", "<:s10:1348291865853689926>", "<:sj:1348291868747628544>", "<:sq:1348291870857498634>",
          "<:sk:1348291873524940890>"],

    "C": ["<:c1:1348291875379085327>", "<:c2:1348291877216194631>", "<:c3:1349083291671859220>", "<:c4:1348291881691250788>",
          "<:c5:1349083293475143700>", "<:c6:1348291885957120001>", "<:c7:1348291887827779615>", "<:c8:1349083289746538496>",
          "<:c9:1348291892600901775>", "<:c10:1349083571784253560>", "<:cj:1348291896535023648>", "<:cq:1348291899940798585>",
          "<:ck:1348291903929716747>"],

    "D": ["<:d1:1348291905578078218>", "<:d2:1349083745059344446>", "<:d3:1348291910212653077>", "<:d4:1348291912276377702>",
          "<:d5:1349083829704462458>", "<:d6:1348291916583931914>", "<:d7:1349083933060632676>", "<:d8:1348291920467857472>",
          "<:d9:1349083935031951450>", "<:d10:1348291924309708880>", "<:dj:1348291926880686151>", "<:dq:1349084118218178651>",
          "<:dk:1348291932576813178>"],

    "H": ["<:h1:1348291934741073960>", "<:h2:1349084217992282162>", "<:h3:1348291940398923900>", "<:h4:1348291943729463388>",
          "<:h5:1348291946627600395>", "<:h6:1349084719337443401>", "<:h7:1348291949664141345>", "<:h8:1348291951161512138>",
          "<:h9:1349084395885035530>", "<:h10:1348291955188174858>", "<:hj:1348291959092936724>", "<:hq:1349084835716661278>",
          "<:hk:1348291962863616000>"]
}

CARD_VALUES = {str(i): i for i in range(2, 11)}
CARD_VALUES.update({"J": 10, "Q": 10, "K": 10, "A": 11})

games = {}

RESULT_TEXTS = {
    "win": "勝ちました！",
    "lose": "負けました...",
    "draw": "引き分けだよ",
    "bust": "バーストで死にました。"
}

def draw_card():
    """ランダムなカードを引く"""
    rank = random.choice(list(CARD_VALUES.keys()))
    suit = random.choice(SUITS)

    if rank == "A":
        emoji = CARD_EMOJIS[suit][0]
    elif rank.isdigit():
        emoji = CARD_EMOJIS[suit][int(rank) - 1]
    else:
        emoji_index = {"J": 10, "Q": 11, "K": 12}[rank]
        emoji = CARD_EMOJIS[suit][emoji_index]

    return (emoji, rank, suit, CARD_VALUES[rank])

def calculate_hand_value(hand):
    """手札の合計値を計算"""
    value = sum(card[3] for card in hand)
    aces = sum(1 for card in hand if card[1] == "A")
    while value > 21 and aces:
        value -= 10
        aces -= 1
    return value

class BlackjackGame:
    def __init__(self, user_id, bet):
        self.user_id = user_id
        self.bet = bet
        self.player_hand = [draw_card(), draw_card()]
        self.dealer_hand = [draw_card(), draw_card()]
        self.finished = False

    def hit(self):
        """プレイヤーがヒットする"""
        if self.finished:
            return None
        self.player_hand.append(draw_card())

        if calculate_hand_value(self.player_hand) > 21:
            self.finished = True  # バースト
            return "bust"
        return self.player_hand

    def dealer_turn(self):
        """ディーラーのターン（高額ベットほど強化）"""
        difficulty_modifier = min(self.bet // 100, 5)  # 100PNCごとに1段階強化（最大5）

        while True:
            dealer_score = calculate_hand_value(self.dealer_hand)

            if dealer_score < 17:
                self.dealer_hand.append(draw_card())  # 通常の動き
            elif dealer_score < 17 + difficulty_modifier:
                if random.random() < 0.5:  # 50% の確率でさらに引く
                    self.dealer_hand.append(draw_card())
                else:
                    break
            else:
                break  # これ以上は引かない

    def get_result(self):
        """勝敗判定"""
        player_score = calculate_hand_value(self.player_hand)
        dealer_score = calculate_hand_value(self.dealer_hand)

        if player_score > 21:
            return "bust"
        if dealer_score > 21 or player_score > dealer_score:
            return "win"
        if player_score < dealer_score:
            return "lose"
        return "draw"

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

    games[user_id] = BlackjackGame(user_id, amount)
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
        if game is None:
            return
        
        if game.hit() == "bust":
            update_user_balance(user_id, -game.bet)
            balance = get_user_balance(user_id)
            await interaction.message.edit(embed=create_blackjack_embed(game, True, discord.Color.red(), result="bust", payout=-game.bet, balance=balance), view=None)
        else:
            await interaction.message.edit(embed=create_blackjack_embed(game, False, BASE_COLOR_CODE))

    @discord.ui.button(label="決定", style=discord.ButtonStyle.red)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        user_id = interaction.user.id
        game = games.get(user_id)
        if game is None:
            return

        game.dealer_turn()
        game.finished = True
        result = game.get_result()

        if result == "draw":
            # update_user_balance(user_id, game.bet)  # PNCを返却
            payout = 0
            emoji = DRAW_EMOJI
            color = BASE_COLOR_CODE
            description = "引き分け！PNCはそのまま返却"
        elif result == "win":
            payout = game.bet * 2
            update_user_balance(user_id, payout)
            emoji = WIN_EMOJI
            color = discord.Color.green()
            description = f"ブラックジャック勝利！+{payout} PNC"
        else:
            payout = -game.bet
            update_user_balance(user_id, payout)
            emoji = LOSE_EMOJI
            color = discord.Color.red()
            description = f"ブラックジャック敗北... -{game.bet} PNC"
            payout = abs(payout)

        balance = get_user_balance(user_id)

        await send_casino_log(interaction, emoji, payout, description, color)

        await interaction.message.edit(
            embed=create_blackjack_embed(game, True, color, result=result, payout=payout, balance=balance),
            view=None
        )