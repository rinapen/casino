import discord
import re
from database.db import get_user_balance
from utils.embed import create_embed
from utils.embed_factory import EmbedFactory
from utils.color import BASE_COLOR_CODE
from config import HITANDBLOW_CATEGORY_ID

class HitAndBlowAcceptButton(discord.ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member, amount: int, timeout=60):
        super().__init__(timeout=timeout)
        self.challenger = challenger
        self.opponent = opponent
        self.amount = amount
        self.accepted = False

    @discord.ui.button(label="承諾する", style=discord.ButtonStyle.success)
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("このボタンはあなた用ではありません。", ephemeral=True)
            return

        self.accepted = True
        await interaction.response.send_message("✅ 勝負を受けました！", ephemeral=True)
        self.stop()

async def on_hitandblow_command(message: discord.Message):
    try:
        pattern = r"\$ヒットアンドブロー\s+<@!?(\d+)>\s+(\d+)"
        match = re.match(pattern, message.content)
        if not match:
            embed = create_embed("", "`$ヒットアンドブロー @ユーザー 掛け金` の形式で入力してください。", discord.Color.red())
            await message.channel.send(embed=embed)
            return

        challenger = message.author
        opponent_id = int(match.group(1))
        amount = int(match.group(2))

        if challenger.id == opponent_id:
            await message.channel.send("自分自身には対戦を申し込めません。")
            return

        opponent = await message.guild.fetch_member(opponent_id)

        # 残高確認
        challenger_balance = get_user_balance(challenger.id)
        opponent_balance = get_user_balance(opponent.id)

        if challenger_balance is None or opponent_balance is None:
            embed = EmbedFactory.not_registered()
            await message.channel.send(embed=embed)
            return

        if challenger_balance < amount:
            embed = EmbedFactory.insufficient_balance(balance=challenger_balance)
            await message.channel.send(embed=embed)
            return

        if opponent_balance < amount:
            embed = create_embed("", f"{opponent.display_name} の残高が不足しています。", discord.Color.red())
            await message.channel.send(embed=embed)
            return

        # 承諾ボタン表示
        view = HitAndBlowAcceptButton(challenger, opponent, amount)
        embed = create_embed(
            title="🎮 ヒットアンドブロー 勝負の申し込み！",
            description=f"{challenger.mention} があなたに {amount} PNC でヒットアンドブローを申し込んでいます。\n\n承諾するには下のボタンを押してください（制限時間：60秒）",
            color=BASE_COLOR_CODE
        )
        await message.channel.send(content=opponent.mention, embed=embed, view=view)

        await view.wait()

        if not view.accepted:
            await message.channel.send("⏳ 時間切れ。対戦はキャンセルされました。")
            return

        # チャンネル作成
        category = message.guild.get_channel(HITANDBLOW_CATEGORY_ID)
        overwrites = {
            message.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            challenger: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            opponent: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            message.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        channel = await message.guild.create_text_channel(
            name=f"hitandblow-{challenger.display_name}-vs-{opponent.display_name}",
            overwrites=overwrites,
            category=category
        )

        await channel.send(f"{challenger.mention} vs {opponent.mention}\nヒットアンドブローを開始します！")

    except Exception as e:
        print(f"[ERROR] on_hitandblow_command: {e}")
        import traceback
        traceback.print_exc()
        embed = create_embed("エラー", "⚠ 処理中にエラーが発生しました。", discord.Color.red())
        await message.channel.send(embed=embed)