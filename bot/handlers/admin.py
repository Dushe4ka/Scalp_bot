from datetime import datetime
from typing import Any

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
    positive_proccess_search_wait_confirm_user_kb,
    positive_proccess_search_wait_confirm_user_kb_with_subscription,
)
from bot.utils.helpers import safe_edit_message
from bot.states.admin_states import AdminStates
from users_repository import db, UsersRepositoryError, ValidationError


router = Router()
logger = setup_logger(__name__)


def _format_dt(dt: Any) -> str:
    """Форматирует datetime из MongoDB (или None) для показа в Telegram."""
    if dt is None:
        return "—"
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d %H:%M")
    return str(dt)

def _format_admin_user_text_by_template(user: dict[str, Any], text_config: dict[str, Any]) -> str:
    template = text_config.get("admin_text", {}).get("user_info")

    subscription_data = user.get("subscription_data") or {}
    subscription = subscription_data.get("subscription")
    subscription_status = "Активна" if subscription else "Не активна"

    return template.format(
        name=user.get("name", "—"),
        tg_id=user.get("tg_id", "—"),
        language=user.get("language", "—"),
        subscription_status=subscription_status,
        current_amount=subscription_data.get("current_amount", "—"),
        subscription_type=subscription_data.get("subscription_type") or "—",
        payment_date=_format_dt(subscription_data.get("payment_date")),
        end_subscription_date=_format_dt(subscription_data.get("end_subscription_date")),
    )


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

    admin_user_id = message.from_user.id
    admin_username = message.from_user.username or ""
    
    text_config = await get_config_lang(lang)
    
    await state.update_data(username_id=username_id)

    user_info_by_username_id = await db.get_user_by_username_or_id(username_id)
    if user_info_by_username_id is None:
        user_not_search = text_config["admin_text"]["user_not_search"]
        await message.answer(
            text=user_not_search,
            reply_markup=(await search_wait_confirm_user_kb(admin_user_id, lang)).as_markup(),
        )
        logger.info(f"Админ {admin_user_id} ({admin_username}) не нашел пользователя {username_id}")
        return

    subscription_data = user_info_by_username_id.get("subscription_data") or {}
    wait_confirm = subscription_data.get("wait_sub_confirmation")
    is_subscriber = subscription_data.get("subscription")

    if wait_confirm and not is_subscriber:
        await state.update_data(tg_id=user_info_by_username_id.get("tg_id"))
        await message.answer(
            _format_admin_user_text_by_template(user_info_by_username_id, text_config),
            reply_markup=(await positive_proccess_search_wait_confirm_user_kb(lang)).as_markup(),
        )
    elif wait_confirm and is_subscriber:
        await state.update_data(tg_id=user_info_by_username_id.get("tg_id"))
        await message.answer(
            _format_admin_user_text_by_template(user_info_by_username_id, text_config),
            reply_markup=(await positive_proccess_search_wait_confirm_user_kb_with_subscription(lang)).as_markup(),
        )
    else:
        user_not_wait_confirm = text_config["admin_text"]["user_not_wait_confirm"]
        await message.answer(
            text=user_not_wait_confirm,
            reply_markup=(await search_wait_confirm_user_kb(admin_user_id, lang)).as_markup(),
        )
    logger.info(f"Админ {admin_user_id} ({admin_username}) ищет пользователя {username_id}")

@router.callback_query(F.data == "confirm_subscription")
async def confirm_subscription(callback: CallbackQuery, state: FSMContext, lang: str):
    """Админ подтверждает подписку пользователю и окно обновляется свежими данными."""
    await callback.answer()
    
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    data = await state.get_data()
    tg_id = data.get("tg_id")
    if tg_id is None:
        await callback.answer("Сначала найдите пользователя.", show_alert=True)
        return

    try:
        await db.admin_check_subscription(int(tg_id))
    except (ValidationError, UsersRepositoryError) as e:
        await callback.answer(f"Не удалось подтвердить: {e}", show_alert=True)
        return

    user = await db.get_user(int(tg_id))
    if user is None:
        await callback.answer("Пользователь не найден в БД.", show_alert=True)
        return

    text_config = await get_config_lang(lang)

    await safe_edit_message(
        callback,
        _format_admin_user_text_by_template(user, text_config),
        reply_markup=(await positive_proccess_search_wait_confirm_user_kb(lang)).as_markup(),
    )
    logger.info(f"Админ {user_id} ({username}) подтвердил подписку пользователю {tg_id}")

@router.callback_query(F.data == "prolong_subscription")
async def prolong_subscription(callback: CallbackQuery, state: FSMContext, lang: str):
    """Админ продлевает подписку пользователю и окно обновляется свежими данными."""
    await callback.answer()

    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    data = await state.get_data()
    tg_id = data.get("tg_id")
    if tg_id is None:
        await callback.answer("Сначала найдите пользователя.", show_alert=True)
        return

    try:
        await db.admin_prolong_subscription(int(tg_id))
    except (ValidationError, UsersRepositoryError) as e:
        await callback.answer(f"Не удалось продлить: {e}", show_alert=True)
        return

    user = await db.get_user(int(tg_id))
    if user is None:
        await callback.answer("Пользователь не найден в БД.", show_alert=True)
        return

    text_config = await get_config_lang(lang)

    await safe_edit_message(
        callback,
        _format_admin_user_text_by_template(user, text_config),
        reply_markup=(await positive_proccess_search_wait_confirm_user_kb_with_subscription(lang)).as_markup(),
    )
    logger.info(f"Админ {user_id} ({username}) продлил подписку пользователю {tg_id}")

@router.callback_query(F.data == "cancel_prolong_subscription")
async def cancel_prolong_subscription(callback: CallbackQuery, state: FSMContext, lang: str):
    """Админ отклоняет продление подписки пользователю и окно обновляется свежими данными."""
    await callback.answer()

    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    data = await state.get_data()
    tg_id = data.get("tg_id")
    if tg_id is None:
        await callback.answer("Сначала найдите пользователя.", show_alert=True)
        return

    try:
        await db.admin_cancel_prolong_subscription(int(tg_id))
    except (ValidationError, UsersRepositoryError) as e:
        await callback.answer(f"Не удалось отклонить: {e}", show_alert=True)
        return

    user = await db.get_user(int(tg_id))
    if user is None:
        await callback.answer("Пользователь не найден в БД.", show_alert=True)
        return

    text_config = await get_config_lang(lang)

    await safe_edit_message(
        callback,
        _format_admin_user_text_by_template(user, text_config),
        reply_markup=(await positive_proccess_search_wait_confirm_user_kb_with_subscription(lang)).as_markup(),
    )

    logger.info(f"Админ {user_id} ({username}) отклонил продление подписки пользователю {tg_id}")

@router.callback_query(F.data == "cancel_subscription")
async def cancel_subscription(callback: CallbackQuery, state: FSMContext, lang: str):
    """Админ отменяет подписку пользователю и окно обновляется свежими данными."""
    await callback.answer()

    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    data = await state.get_data()
    tg_id = data.get("tg_id")
    if tg_id is None:
        await callback.answer("Сначала найдите пользователя.", show_alert=True)
        return

    try:
        await db.admin_cancel_subscription(int(tg_id))
    except (ValidationError, UsersRepositoryError) as e:
        await callback.answer(f"Не удалось отменить: {e}", show_alert=True)
        return

    user = await db.get_user(int(tg_id))
    if user is None:
        await callback.answer("Пользователь не найден в БД.", show_alert=True)
        return

    text_config = await get_config_lang(lang)

    await safe_edit_message(
        callback,
        _format_admin_user_text_by_template(user, text_config),
        reply_markup=(await positive_proccess_search_wait_confirm_user_kb(lang)).as_markup(),
    )

    logger.info(f"Админ {user_id} ({username}) отклонил подписку пользователю {tg_id}")