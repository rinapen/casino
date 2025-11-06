"""
カジノボットの設定ファイル
環境変数から設定を読み込み、デフォルト値を提供します
"""
import os
from typing import Final
from dotenv import load_dotenv
import pytz

load_dotenv()


# ========================================
# ヘルパー関数
# ========================================
def safe_get_int_env(key: str, default: int = 0) -> int:
    """
    環境変数を安全に整数として取得
    
    Args:
        key: 環境変数名
        default: デフォルト値
    
    Returns:
        環境変数の値（整数）、無効な場合はデフォルト値
    """
    value = os.getenv(key)
    
    if not value or value.startswith("your_") or value.startswith("YOUR_"):
        if value:
            print(f"[WARN] 環境変数 {key} が設定されていません（プレースホルダー値: {value}）。デフォルト値 {default} を使用します。")
        else:
            print(f"[WARN] 環境変数 {key} が設定されていません。デフォルト値 {default} を使用します。")
        return default
    
    try:
        return int(value)
    except ValueError:
        print(f"[WARN] 環境変数 {key} の値 '{value}' が無効です。デフォルト値 {default} を使用します。")
        return default


def safe_get_str_env(key: str, default: str | None = None) -> str | None:
    """
    環境変数を安全に文字列として取得
    
    Args:
        key: 環境変数名
        default: デフォルト値
    
    Returns:
        環境変数の値、無効な場合はデフォルト値
    """
    value = os.getenv(key)
    
    if not value or value.startswith("your_") or value.startswith("YOUR_"):
        if value:
            print(f"[WARN] 環境変数 {key} が設定されていません（プレースホルダー値: {value}）。デフォルト値を使用します。")
        else:
            print(f"[WARN] 環境変数 {key} が設定されていません。デフォルト値を使用します。")
        return default
    
    return value

# ========================================
# データベース設定
# ========================================
def safe_get_mongo_uri() -> str:
    """MongoDB URIを安全に取得"""
    value = safe_get_str_env("MONGO_URI", "mongodb://localhost:27017/")
    return value if value else "mongodb://localhost:27017/"

def safe_get_db_name() -> str:
    """データベース名を安全に取得"""
    value = safe_get_str_env("DB_NAME", "paypay_bot")
    return value if value else "paypay_bot"

MONGO_URI: Final[str] = safe_get_mongo_uri()
DB_NAME: Final[str] = safe_get_db_name()

# コレクション名
TOKENS_COLLECTION: Final[str] = os.getenv("TOKENS_COLLECTION", "tokens")
USERS_COLLECTION: Final[str] = os.getenv("USERS_COLLECTION", "users")
SETTINGS_COLLECTION: Final[str] = os.getenv("SETTINGS_COLLECTION", "settings")
CASINO_STATS_COLLECTION: Final[str] = os.getenv("CASINO_STATS_COLLECTION", "casino_stats")
MODELS_COLLECTION: Final[str] = os.getenv("MODELS_COLLECTION", "models")
BLACKJACK_LOGS_COLLECTION: Final[str] = os.getenv("BLACKJACK_LOGS_COLLECTION", "blackjack_logs")
USER_TRANSACTIONS_COLLECTION: Final[str] = os.getenv("USER_TRANSACTIONS_COLLECTION", "user_transactions")
CASINO_TRANSACTION_COLLECTION: Final[str] = os.getenv("CASINO_TRANSACTION_COLLECTION", "casino_transactions")
BET_HISTORY_COLLECTION: Final[str] = os.getenv("BET_HISTORY_COLLECTION", "bet_history")
BOT_STATE_COLLECTION: Final[str] = os.getenv("BOT_STATE_COLLECTION", "bot_state")
BLACKLIST_COLLECTION: Final[str] = os.getenv("BLACKLIST_COLLECTION", "blacklist")

# ========================================
# 経済設定
# ========================================
MIN_INITIAL_DEPOSIT: Final[int] = 100  # 初期入金の最低金額
TAX_RATE: Final[float] = 0.1  # 10% の税金
FEE_RATE: Final[float] = 0.05  # 5% の手数料
PAYOUT_MIN_JPY: Final[int] = 100
PAYOUT_MIN_PNC: Final[int] = PAYOUT_MIN_JPY * 10
PAYOUT_DISABLED: Final[bool] = True

# ========================================
# PayPay設定
# ========================================
PAYPAY_ICON_URL: Final[str] = "https://cdn.discordapp.com/attachments/1219916908485283880/1380606272629637271/AieC1ypSSh_2rctvrNtVggyFRP9cNtvnEIPkVmzZGFlhN8bNdHCl3GZbxK7O8vCe7A.png?ex=68447d49&is=68432bc9&hm=fa35f7815dfffd5d0b5ec152538ce2ab4b4031079d3dcdaf67c71fb591714f4a&"
PAYPAY_LINK_REGEX: Final[str] = r"https://pay\.paypay\.ne\.jp/[a-zA-Z0-9]+"

# ========================================
# パス設定
# ========================================
DICE_FOLDER: Final[str] = "assets/dice"

# ========================================
# Discord設定
# ========================================
GUILD_ID: Final[int] = safe_get_int_env("GUILD_ID", 0)
ACCOUNT_CHANNEL_ID: Final[int] = safe_get_int_env("ACCOUNT_CHANNEL_ID", 0)
INVITE_PANEL_CHANNEL_ID: Final[int] = safe_get_int_env("INVITE_PANEL_CHANNEL_ID", 0)
HITANDBLOW_CATEGORY_ID: Final[int] = safe_get_int_env("HITANDBLOW_CATEGORY_ID", 0)

# ========================================
# アセットURL
# ========================================
FLIP_GIF_URL: Final[str] = "https://cdn.discordapp.com/attachments/1219916908485283880/1383914774131376270/U4ObEcJW9ksvEN6tCmsf1750021234-1750021370.gif?ex=68508692&is=684f3512&hm=7370c85f4237840cf3b769c29f51f2cb60033e351e934206a2bbab75209d77fc&"
THUMBNAIL_URL: Final[str] = "https://cdn.discordapp.com/attachments/1219916908485283880/1386322194111533147/ChatGPT_Image_2025622_21_28_04.png?ex=685948a7&is=6857f727&hm=548ff6d889653c59ec69f641efc2c21192c6cdb2c0798ae2c5d2d3cc289a38dd&"
FRONT_IMG: Final[str] = "https://cdn.discordapp.com/attachments/1219916908485283880/1383915331185020989/0.png?ex=68508716&is=684f3596&hm=1da630e3b7a3447d7c72e434c2b8626775063a1b2b4f58abbb595f2d2bafa3ee&"
BACK_IMG: Final[str] = "https://cdn.discordapp.com/attachments/1219916908485283880/1383915330933620796/23.png?ex=68508716&is=684f3596&hm=ba04bb357d7656faf58734b0f94af17e2463cd00a356bb74e0a338044ea47bd5&"

# ========================================
# タイムゾーン設定
# ========================================
JST: Final = pytz.timezone("Asia/Tokyo")

# ========================================
# ゲームアセット
# ========================================
CARD_EMOJIS: Final[dict[str, list[str]]] = {
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

# ========================================
# 環境モード設定
# ========================================
ENVIRONMENT: Final[str] = os.getenv("ENVIRONMENT", "test")  # "test" or "production"
IS_TEST_MODE: Final[bool] = ENVIRONMENT.lower() == "test"
IS_PRODUCTION_MODE: Final[bool] = ENVIRONMENT.lower() == "production"

# ========================================
# 認証情報（環境変数から取得）
# ========================================
TOKEN: Final[str | None] = safe_get_str_env("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("[ERROR] DISCORD_BOT_TOKEN が設定されていません。ボットは起動できませんが、設定チェックは続行します。")

# PayPay設定（本番環境のみ使用）
PAYPAY_PHONE_NUMBER: Final[str | None] = (
    safe_get_str_env("PAYPAY_PHONE_NUMBER") if IS_PRODUCTION_MODE else None
)
PAYPAY_PIN: Final[str | None] = (
    safe_get_str_env("PAYPAY_PIN") if IS_PRODUCTION_MODE else None
)

# ========================================
# 管理者・除外ユーザーID
# ========================================
def safe_get_admin_user_id() -> int | None:
    """管理者ユーザーIDを安全に取得"""
    value = os.getenv("ADMIN_USER_ID")
    
    if not value or value.startswith("your_") or value.startswith("YOUR_"):
        if value:
            print(f"[WARN] 環境変数 ADMIN_USER_ID が設定されていません（プレースホルダー値: {value}）。管理者機能が無効化されます。")
        else:
            print(f"[WARN] 環境変数 ADMIN_USER_ID が設定されていません。管理者機能が無効化されます。")
        return None
    
    try:
        return int(value)
    except ValueError:
        print(f"[WARN] 環境変数 ADMIN_USER_ID の値 '{value}' が無効です。管理者機能が無効化されます。")
        return None

ADMIN_USER_ID: Final[int | None] = safe_get_admin_user_id()


def safe_get_excluded_user_ids() -> list[int]:
    """除外ユーザーIDリストを安全に取得"""
    value = os.getenv("EXCLUDED_USER_IDS", "")
    
    if not value or value.startswith("your_") or value.startswith("YOUR_"):
        if value:
            print(f"[WARN] 環境変数 EXCLUDED_USER_IDS が設定されていません（プレースホルダー値: {value}）。除外ユーザーなしで動作します。")
        return []
    
    try:
        ids = [int(uid.strip()) for uid in value.split(",") if uid.strip()]
        return ids
    except ValueError as e:
        print(f"[WARN] 環境変数 EXCLUDED_USER_IDS の値 '{value}' が無効です。除外ユーザーなしで動作します。エラー: {e}")
        return []

EXCLUDED_USER_IDS: Final[list[int]] = safe_get_excluded_user_ids()

# ========================================
# ログチャンネルID（環境変数から取得）
# ========================================
CASINO_LOG_CHANNEL_ID: Final[str | None] = safe_get_str_env("CASINO_LOG_CHANNEL_ID")
PAYIN_LOG_CHANNEL_ID: Final[str | None] = safe_get_str_env("PAYIN_LOG_CHANNEL_ID")
PAYOUT_LOG_CHANNEL_ID: Final[str | None] = safe_get_str_env("PAYOUT_LOG_CHANNEL_ID")
RANKING_CHANNEL_ID: Final[str | None] = safe_get_str_env("RANKING_CHANNEL_ID")
ADMIN_CHANNEL_ID: Final[str | None] = safe_get_str_env("ADMIN_CHANNEL_ID")