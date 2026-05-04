import os
import dotenv

dotenv.load_dotenv()

# ✅ Преобразуем строку из .env в булево значение
USE_DEMO_STR = os.getenv("USE_DEMO", "False").strip().lower()
USE_DEMO = USE_DEMO_STR in ("true", "1", "yes")

# Режим маржи аккаунта для UTA:
# - CROSS / REGULAR / REGULAR_MARGIN
# - ISOLATED / ISOLATED_MARGIN
TRADING_MARGIN_MODE = (os.getenv("MARGIN_MODE", "CROSS") or "CROSS").strip().upper()

# Поддержка двух форматов env-ключей:
# - новый: MONGO_URI / MONGO_DB
# - legacy: MONGODB_URI / MONGODB_DB
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or "mongodb://localhost:27017"
MONGO_DB = os.getenv("MONGO_DB") or os.getenv("MONGODB_DB") or "scalp_bot"

# Даннные для Telegram бота
TELEGRAM_BOT_TOKEN=os.getenv("TELEGRAM_BOT_TOKEN")
URL_TGCHANNEL=os.getenv("URL_TGCHANNEL")
URL_PAYMENT=os.getenv("URL_PAYMENT")
ADMIN_CHAT_ID=os.getenv("ADMIN_CHAT_ID")
URL_TECH_SUPPORT=os.getenv("URL_TECH_SUPPORT")

# Поддержка нескольких админов: ADMIN_IDS=1,2,3
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = {
    int(x.strip())
    for x in ADMIN_IDS_RAW.split(",")
    if x.strip().isdigit()
}

# Локальный URL для внутренних запросов проекта (бот -> API, админка -> API)
LOCAL_SERVER_URL = os.getenv("LOCAL_SERVER_URL", "http://127.0.0.1:8050")

# Публичный URL (для уведомлений/показа внешних эндпоинтов)
SERVER_URL = os.getenv("SERVER_URL", LOCAL_SERVER_URL)
