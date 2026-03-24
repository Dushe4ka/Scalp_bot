from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from logger_config import setup_logger
from bot.languages._lang_func import get_config_lang
from bot.keyboards.inline_kb import admin_menu_kb, users_list_kb, wait_confirm_kb
from bot.utils.helpers import safe_edit_message


router = Router()
logger = setup_logger(__name__)

@router.message(Command("admin"))
async def admin_start(message: Message, lang: str):
    """Обработка команды /admin"""
    user_id = message.from_user.id
    username = message.from_user.username or ""

    text_config = await get_config_lang(lang)
    text = text_config["admin_text"]["admin_menu"]

    await message.answer(
        text,
        reply_markup=(await admin_menu_kb(user_id, lang)).as_markup()
    )
    logger.info(f"Пользователь {user_id} ({username}) открыл админ-панель")

@router.callback_query(F.data == "admin_menu")
async def admin_menu(callback: CallbackQuery, lang: str):
    """Обработка нажатия на кнопку "Админ-панель"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    text_config = await get_config_lang(lang)
    text = text_config["admin_text"]["admin_menu"]

    await safe_edit_message(
        callback,
        text,
        reply_markup=(await admin_menu_kb(user_id, lang)).as_markup()
    )
    logger.info(f"Пользователь {user_id} ({username}) открыл админ-панель")

@router.callback_query(F.data == "users_list")
async def users_list(callback: CallbackQuery, lang: str):
    """Обработка нажатия на кнопку "Список пользователей"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    text_config = await get_config_lang(lang)
    text = text_config["admin_text"]["users_list"]

    await safe_edit_message(
        callback,
        text,
        reply_markup=(await users_list_kb(user_id, lang)).as_markup())
    logger.info(f"Пользователь {user_id} ({username}) открыл список пользователей")

@router.callback_query(F.data == "wait_confirm")
async def wait_confirm(callback: CallbackQuery, lang: str):
    """Обработка нажатия на кнопку "Ожидающие подтверждения"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    text_config = await get_config_lang(lang)
    text = text_config["admin_text"]["wait_confirm"]

    await safe_edit_message(
        callback,
        text,
        reply_markup=(await wait_confirm_kb(user_id, lang)).as_markup())
    logger.info(f"Пользователь {user_id} ({username}) открыл список ожидающих подтверждения")