from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from bot.keyboards.inline_kb import (
    start_menu_kb, 
    russia_start_kb, 
    english_start_kb, 
    greeting_kb,
    russia_start_kb_wait_confirm_subscription,
    russia_start_kb_with_subscription,
    english_start_kb_wait_confirm_subscription,
    english_start_kb_with_subscription,
    greeting_kb_wait_confirm_subscription,
    greeting_kb_with_subscription
)
from logger_config import setup_logger
from bot.utils.helpers import safe_edit_message
from database.users_repository import db
from bot.languages._lang_func import get_config_lang

router = Router()
logger = setup_logger(__name__)

# Обработчик команды /start
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Обработка команд /start"""
    user_id = message.from_user.id
    username = message.from_user.username or ""
    
    await state.clear()
    await db.get_or_create_user(user_id, username)

    text = "Выберите язык / Choose language:"
    
    await message.answer(
        text,
        reply_markup=start_menu_kb(user_id).as_markup()
    )
    logger.info(f"Пользователь {user_id} ({username}) открыл главное меню")

# Обработчик команды /main_menu
@router.message(Command("main_menu"))
async def cmd_main_menu(message: Message, state: FSMContext, lang):
    """Обработка команд /main_menu"""
    user_id = message.from_user.id
    username = message.from_user.username or ""
    
    await state.clear()
    text_config = await get_config_lang(lang)
    text = text_config["start_text"]["greeting"]

    wait_confirm = await db.is_wait_sub_confirmation(user_id)
    is_subscriber = await db.is_subscriber(user_id)

    if wait_confirm and not is_subscriber:
        reply_markup = (await greeting_kb_wait_confirm_subscription(user_id, lang)).as_markup()
    elif wait_confirm and is_subscriber:
        reply_markup = (await greeting_kb_wait_confirm_subscription(user_id, lang)).as_markup()
    elif not wait_confirm and is_subscriber:
        reply_markup = (await greeting_kb_with_subscription(user_id, lang)).as_markup()
    else:
        reply_markup = (await greeting_kb(user_id, lang)).as_markup()

    await message.answer(
        text,
        reply_markup=reply_markup
    )
    logger.info(f"Пользователь {user_id} ({username}) открыл главное меню")

@router.callback_query(F.data == "start_menu")
async def start_menu(callback: CallbackQuery):
    """Обработка нажатия на кнопку "Назад" в главном меню"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    
    text = "Выберите язык / Choose language:"

    await safe_edit_message(
        callback,
        text,
        reply_markup=start_menu_kb(user_id).as_markup()
    )
    logger.info(f"Пользователь {user_id} ({username}) вернулся к главному меню")

# Обработчик нажатия на кнопку "Русский"
@router.callback_query(F.data == "russian_lang")
async def russia_start(callback: CallbackQuery):
    """
    Обработка нажатия на кнопку "Русский"
    """
    user_id = callback.from_user.id
    await db.update_language(user_id, "ru")
    username = callback.from_user.username or ""

    text = " Здравствуйте! Меня зовут ZdormanBot 👋 \nЯ вам расскажу как приобрести подписку на наш сервис 📈 \n И почему нам стоит верить 😎"
    wait_confirm = await db.is_wait_sub_confirmation(user_id)
    is_subscriber = await db.is_subscriber(user_id)

    if wait_confirm and not is_subscriber:
        reply_markup = russia_start_kb_wait_confirm_subscription(user_id).as_markup()
    elif wait_confirm and is_subscriber:
        reply_markup = russia_start_kb_wait_confirm_subscription(user_id).as_markup()
    elif not wait_confirm and is_subscriber:
        reply_markup = russia_start_kb_with_subscription(user_id).as_markup()
    else:
        reply_markup = russia_start_kb(user_id).as_markup()

    await safe_edit_message(
        callback,
        text,
        reply_markup=reply_markup
    )
    logger.info(f"Пользователь {user_id} ({username}) выбрал русский язык")

# Обработчик нажатия на кнопку "Английский"
@router.callback_query(F.data == "english_lang")
async def english_start(callback: CallbackQuery):
    """
    Обработка нажатия на кнопку "English"
    """
    user_id = callback.from_user.id
    await db.update_language(user_id, "en")
    username = callback.from_user.username or ""

    text = "Hello! My name is ZdormanBot 👋 \nI will tell you how to buy a subscription to our service 📈 \nAnd why we should be trusted 😎"
    wait_confirm = await db.is_wait_sub_confirmation(user_id)
    is_subscriber = await db.is_subscriber(user_id)

    if wait_confirm and not is_subscriber:
        reply_markup = english_start_kb_wait_confirm_subscription(user_id).as_markup()
    elif wait_confirm and is_subscriber:
        reply_markup = english_start_kb_wait_confirm_subscription(user_id).as_markup()
    elif not wait_confirm and is_subscriber:
        reply_markup = english_start_kb_with_subscription(user_id).as_markup()
    else:
        reply_markup = english_start_kb(user_id).as_markup()

    await safe_edit_message(
        callback,
        text,
        reply_markup=reply_markup
    )
    logger.info(f"Пользователь {user_id} ({username}) выбрал английский язык")

@router.callback_query(F.data == "greeting")
async def greeting(callback: CallbackQuery, lang: str):
    """
    Обработка нажатия на кнопку "Приветствие"
    """
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    
    text_config = await get_config_lang(lang)
    text = text_config["start_text"]["greeting"]

    wait_confirm = await db.is_wait_sub_confirmation(user_id)
    is_subscriber = await db.is_subscriber(user_id)

    if wait_confirm and not is_subscriber:
        reply_markup = (await greeting_kb_wait_confirm_subscription(user_id, lang)).as_markup()
    elif wait_confirm and is_subscriber:
        reply_markup = (await greeting_kb_wait_confirm_subscription(user_id, lang)).as_markup()
    elif not wait_confirm and is_subscriber:
        reply_markup = (await greeting_kb_with_subscription(user_id, lang)).as_markup()
    else:
        reply_markup = (await greeting_kb(user_id, lang)).as_markup()

    await safe_edit_message(
        callback,
        text,
        reply_markup=reply_markup
    )
    logger.info(f"Пользователь {user_id} ({username}) открыл главное меню")