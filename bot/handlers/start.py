from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from bot.keyboards.inline_kb import main_menu_kb
from logger_config import setup_logger

router = Router()
logger = setup_logger(__name__)

@router.message(Command("start", "main_menu"))
async def cmd_start(message: Message):
    """Обработка команд /start и /main_menu"""
    user_id = message.from_user.id
    username = message.from_user.username or ""
    
    text = "👋 Добро пожаловать в Scalp Bot!\n\nВыберите действие:"
    
    await message.answer(
        text,
        reply_markup=main_menu_kb(user_id).as_markup()
    )
    logger.info(f"Пользователь {user_id} ({username}) открыл главное меню")

