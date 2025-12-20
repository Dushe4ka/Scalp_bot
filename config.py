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