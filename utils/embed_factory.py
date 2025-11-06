import discord
from utils.embed import create_embed
from config import ACCOUNT_CHANNEL_ID
from utils.emojis import PNC_EMOJI_STR
class EmbedFactory:
    @staticmethod
    def already_registered():
        return create_embed("登録済みです", "あなたはすでにアカウントを紐づけています。", discord.Color.red())

    @staticmethod
    def registration_prompt(amount: int):
        return create_embed(
            "登録受付け",
            f"### **20秒以内に**{amount}**円のPayPayリンクを送信してください。**",
            discord.Color.orange()
        )
    
    @staticmethod
    def require_registration_prompt():
        return create_embed(
            "",
            f"あなたはアカウントを紐付けていません。<#{ACCOUNT_CHANNEL_ID}>のパネルから登録してください。",
            discord.Color.red()
        )
    
    @staticmethod
    def balance_display(balance: int):
        return discord.Embed(
            description=f"# {PNC_EMOJI_STR}`{balance:,}`",
            color=discord.Color.green()
        )
    
    @staticmethod
    def bet_too_low(min_bet: int = 100):
        return create_embed(
            "",
            f"ベット額は{min_bet}以上にしてください。",
            discord.Color.red()
        )
    
    @staticmethod
    def insufficient_balance(balance: int):
        return create_embed(
            "",
            f"残高不足です。現在の残高: {PNC_EMOJI_STR}`{balance:,}`",
            discord.Color.red()
        )
        
    @staticmethod
    def error(message="予期せぬエラーが発生しました"):
        return create_embed("❌ エラー", message, discord.Color.red())

    @staticmethod
    def success(title="✅ 成功", message="操作が正常に完了しました"):
        return create_embed(title, message, discord.Color.green())

    @staticmethod
    def warning(message="⚠️ 注意が必要です"):
        return create_embed("⚠️ 警告", message, discord.Color.yellow())

    @staticmethod
    def not_registered():
        return create_embed("未登録アカウント", "この操作にはアカウントの登録が必要です。", discord.Color.red())