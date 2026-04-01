import os
import dotenv

dotenv.load_dotenv()

# ✅ Преобразуем строку из .env в булево значение
USE_DEMO_STR = os.getenv("USE_DEMO", "False").strip().lower()
USE_DEMO = USE_DEMO_STR in ("true", "1", "yes")

MONGO_URI = os.getenv("MONGO_URI","mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "scalp_bot")

# Данные для сервера Scalp_bot
NGROK_TOKEN=os.getenv("NGROK_TOKEN")

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

# URL сервера Scalp_bot_api
SERVER_URL = os.getenv("SERVER_URL", "http://127.0.0.1:8050")
