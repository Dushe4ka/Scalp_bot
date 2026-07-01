from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from bot.keyboards.inline_kb import start_menu_kb, help_kb
from logger_config import setup_logger
from bot.utils.helpers import safe_edit_message
from bot.utils.main_menu import build_main_menu_view, build_welcome_about_text
from database.users_repository import db
from bot.languages._lang_func import get_config_lang

router = Router()
logger = setup_logger(__name__)


async def _send_language_picker(target, user_id: int, *, edit: bool = False) -> None:
    cfg = await get_config_lang("ru")
    text = cfg["start_text"]["choose_language"]
    markup = start_menu_kb(user_id).as_markup()
    if edit:
        await safe_edit_message(target, text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)


async def _send_main_menu(
    target,
    user_id: int,
    lang: str,
    *,
    edit: bool = False,
    split_welcome: bool = False,
) -> None:
    if split_welcome:
        about_text = await build_welcome_about_text(lang)
        menu_text, markup = await build_main_menu_view(
            user_id, lang, help_intro_key="greeting_help_first",
        )
        if isinstance(target, CallbackQuery):
            await safe_edit_message(target, about_text)
            await target.message.answer(menu_text, reply_markup=markup)
        else:
            await target.answer(about_text)
            await target.answer(menu_text, reply_markup=markup)
        return

    text, markup = await build_main_menu_view(user_id, lang)
    if edit:
        await safe_edit_message(target, text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)


def _build_help_text(cfg: dict) -> str:
    st = cfg["start_text"]
    return "\n\n".join([
        cfg["general"]["help_title"],
        st["greeting"],
        st["welcome_intro"],
        st["greeting_help"],
        cfg["general"]["help_setup"],
        cfg["general"]["help_commands"],
    ])


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, lang: str):
    """Обработка команд /start"""
    user_id = message.from_user.id
    username = message.from_user.username or ""

    await state.clear()
    user = await db.get_or_create_user(user_id, username)

    if user.get("language_selected"):
        await _send_main_menu(message, user_id, lang)
    else:
        await _send_language_picker(message, user_id)

    logger.info("Пользователь %s (%s) открыл /start", user_id, username)


@router.message(Command("main_menu"))
async def cmd_main_menu(message: Message, state: FSMContext, lang: str):
    """Обработка команд /main_menu"""
    user_id = message.from_user.id
    username = message.from_user.username or ""

    await state.clear()
    user = await db.get_or_create_user(user_id, username)

    if not user.get("language_selected"):
        await _send_language_picker(message, user_id)
        return

    await _send_main_menu(message, user_id, lang)
    logger.info("Пользователь %s (%s) открыл главное меню", user_id, username)


@router.message(Command("help"))
async def cmd_help(message: Message, lang: str):
    """Справка по боту."""
    cfg = await get_config_lang(lang)
    await message.answer(
        _build_help_text(cfg),
        reply_markup=(await help_kb(lang)).as_markup(),
    )


@router.callback_query(F.data == "start_menu")
async def start_menu(callback: CallbackQuery):
    """Смена языка (не сбрасывает весь путь пользователя)."""
    user_id = callback.from_user.id
    await callback.answer()
    await _send_language_picker(callback, user_id, edit=True)
    logger.info("Пользователь %s открыл выбор языка", user_id)


@router.callback_query(F.data == "russian_lang")
async def russia_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    first_time = not bool((user or {}).get("language_selected"))
    await db.update_language(user_id, "ru")
    await state.clear()
    await callback.answer()
    if first_time:
        await _send_main_menu(callback, user_id, "ru", split_welcome=True)
    else:
        await _send_main_menu(callback, user_id, "ru", edit=True)
    logger.info("Пользователь %s выбрал русский язык", user_id)


@router.callback_query(F.data == "english_lang")
async def english_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    first_time = not bool((user or {}).get("language_selected"))
    await db.update_language(user_id, "en")
    await state.clear()
    await callback.answer()
    if first_time:
        await _send_main_menu(callback, user_id, "en", split_welcome=True)
    else:
        await _send_main_menu(callback, user_id, "en", edit=True)
    logger.info("Пользователь %s выбрал английский язык", user_id)


@router.callback_query(F.data == "greeting")
async def greeting(callback: CallbackQuery, state: FSMContext, lang: str):
    """Главное меню (callback)."""
    user_id = callback.from_user.id
    await state.clear()
    await callback.answer()
    await _send_main_menu(callback, user_id, lang, edit=True)
    logger.info("Пользователь %s открыл главное меню", user_id)
