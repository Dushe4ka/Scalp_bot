from re import A
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from logger_config import setup_logger
from bot.languages._lang_func import get_config_lang
from bot.keyboards.inline_kb import (
    admin_menu_kb, 
    users_list_kb, 
    wait_confirm_kb,
    search_wait_confirm_user_kb,
    proccess_search_wait_confirm_user_kb,
)
from bot.utils.helpers import safe_edit_message
from bot.states.admin_states import AdminStates
from users_repository import db


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
async def wait_confirm(callback: CallbackQuery, state: FSMContext, lang: str):
    """Обработка нажатия на кнопку "Ожидающие подтверждения"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    await state.clear()

    text_config = await get_config_lang(lang)
    text = text_config["admin_text"]["wait_confirm"]

    await safe_edit_message(
        callback,
        text,
        reply_markup=(await wait_confirm_kb(user_id, lang)).as_markup())
    logger.info(f"Пользователь {user_id} ({username}) открыл список ожидающих подтверждения")

@router.callback_query(F.data == "search_by_username_id")
async def search_by_username_id(callback: CallbackQuery, state: FSMContext, lang: str):
    """Обработка нажатия на кнопку "Ввести username или ID пользователя"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    text_config = await get_config_lang(lang)
    text = text_config["admin_text"]["search_by_username_id"]

    await state.set_state(AdminStates.wait_confirm_user)

    await safe_edit_message(
        callback,
        text,
        reply_markup=(await search_wait_confirm_user_kb(user_id, lang)).as_markup())
    logger.info(f"Пользователь {user_id} ({username}) ищет пользователя ")

@router.message(AdminStates.wait_confirm_user, F.text)
async def process_search_by_username_id(message: Message, state: FSMContext, lang: str):
    """Админ прислал username или id пользователя, ожидающего подтверждение"""
    username_id = message.text.strip()
    
    text_config = await get_config_lang(lang)
    
    await state.update_data(username_id=username_id)

    user_info_by_username_id = await db.get_user_by_username_or_id(username_id)

    if user_info_by_username_id != None:
        await message.answer(
            user_info_by_username_id,
            reply_markup=(await proccess_search_wait_confirm_user_kb(lang)).as_markup())
    else:
        user_not_search = text_config["admin_text"]["user_not_search"]
        await message.answer(
            text=user_not_search,
            reply_markup=(await proccess_search_wait_confirm_user_kb(lang)).as_markup())
