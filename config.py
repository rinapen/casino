import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DB_NAME", "paypay_bot")
TOKENS_COLLECTION = os.getenv("TOKENS_COLLECTION", "tokens")
USERS_COLLECTION = os.getenv("USERS_COLLECTION", "users")
SETTINGS_COLLECTION = os.getenv("SETTINGS_COLLECTION", "settings")
CASINO_STATS_COLLECTION = os.getenv("CASINO_STATS_COLLECTION", "casino_stats")
MODELS_COLLECTION = os.getenv("MODELS_COLLECTION", "models")

USER_TRANSACTIONS_COLLECTION = os.getenv("USER_TRANSACTIONS_COLLECTION", "user_transactions")
CASINO_TRANSACTION_COLLECTION = os.getenv("CASINO_TRANSACTION_COLLECTION", "casino_transactions")

MIN_INITIAL_DEPOSIT = 100  # 初期入金の最低金額
TAX_RATE = 0.1  # 10% の税金
FEE_RATE = 0.05  # 5% の手数料

BASE_COLOR_CODE=0x2b2d31
PAYPAY_ICON_URL="https://cdn.discordapp.com/attachments/1338813178674413591/1349042174083207280/unnamed.png?ex=67d1a8ee&is=67d0576e&hm=f3e0c4c9b88a9f68a3f20e35bb4c6236c33e42acea7ee14ab9d9c71257c00a21&"
PAYPAY_LINK_REGEX = r"^https://pay\.paypay\.ne\.jp/[a-zA-Z0-9]+$"

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PAYPAY_PHONE = os.getenv("PAYPAY_PHONE")
PAYPAY_PASSWORD = os.getenv("PAYPAY_PASSWORD")

ADMIN_CHANNEL_ID = os.getenv("ADMIN_CHANNEL_ID")
CASINO_LOG_CHANNEL_ID = os.getenv("CASINO_LOG_CHANNEL_ID")
PAYPAY_LOG_CHANNEL_ID = os.getenv("PAYPAY_LOG_CHANNEL_ID")

WIN_EMOJI = os.getenv("WIN_EMOJI")
LOSE_EMOJI = os.getenv("LOSE_EMOJI")