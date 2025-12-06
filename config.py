import os
import dotenv

dotenv.load_dotenv()

MONGO_URI = os.getenv("MONGO_URI","mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "scalp_bot")

# Данные для сервера Scalp_bot
NGROK_TOKEN=os.getenv("NGROK_TOKEN")

# Даннные для Telegram бота
TELEGRAM_BOT_TOKEN=os.getenv("TELEGRAM_BOT_TOKEN")