from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from bot.config import TELEGRAM_BOT_TOKEN, TEST_TELEGRAM_BOT_TOKEN
from datetime import datetime
from typing import Any

def _format_dt(dt: Any) -> str:
    """Форматирует datetime из MongoDB (или None) для показа в Telegram."""
    if dt is None:
        return "—"
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d %H:%M")
    return str(dt)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)