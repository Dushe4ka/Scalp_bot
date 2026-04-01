from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from bot.keyboards.inline_kb import (
    profile_menu_kb_without_subscription, 
    profile_menu_kb,
    profile_menu_wait_sub_confirmation_kb_without_subscription,
    profile_menu_wait_sub_confirmation_kb_with_subscription,
    profile_statistics_kb,
    profile_settings_kb,
    back_to_profile_settings_kb,
)
from logger_config import setup_logger
from bot.utils.helpers import safe_edit_message
from bot.utils.misc import _format_dt
from users_repository import db, UsersRepositoryError, ValidationError
from bot.languages._lang_func import get_config_lang
from bot.states.profile_states import ProfileStates
from typing import Any

router = Router()
logger = setup_logger(__name__)

def _format_key_secret(key_secret: str) -> str:
    """Форматирует текст API ключа/секрета на первые 6 символов и последние 4 символа"""
    if len(key_secret) < 10:
        return key_secret
    else:
        return f"{key_secret[:6]}...{key_secret[-4:]}"

async def _format_profile_text_by_template(user: dict[str, Any], text_config: dict[str, Any], type_settings: str) -> str:
    """Форматирует текст профиля по шаблону"""
    if type_settings == "profile_menu":
        template = text_config.get("profile_text", {}).get("profile_menu")

        payment_date = _format_dt(user["subscription_data"]["payment_date"])
        subscription_type = user["subscription_data"]["subscription_type"]
        sum_for_trades = user["bybit_data"]["sum_for_trades"]
        api_key = '✅' if user["bybit_data"]["api_key"] else '❌'

        return template.format(
            payment_date=payment_date, 
            subscription_type=subscription_type, 
            sum_for_trades=sum_for_trades, 
            api_key=api_key)

    elif type_settings == "profile_statistics":
        template = text_config.get("profile_text", {}).get("profile_statistics")

        total_trades = user["statistics"]["total_trades"]
        total_pnl = user["statistics"]["total_pnl"]
        positive_trades = user["statistics"]["positive_trades"]
        sum_positive_trades = user["statistics"]["sum_positive_trades"]
        negative_trades = user["statistics"]["negative_trades"]
        sum_negative_trades = user["statistics"]["sum_negative_trades"]

        return template.format(
            total_trades=total_trades, 
            total_pnl=total_pnl, 
            positive_trades=positive_trades, 
            sum_positive_trades=sum_positive_trades, 
            negative_trades=negative_trades, 
            sum_negative_trades=sum_negative_trades)

    elif type_settings == "profile_settings":
        template = text_config.get("profile_text", {}).get("profile_settings")

        api_key = _format_key_secret(user["bybit_data"]["api_key"])
        api_secret = _format_key_secret(user["bybit_data"]["api_secret"])
        sum_for_trades = user["bybit_data"]["sum_for_trades"]

        return template.format(
            api_key=api_key, 
            api_secret=api_secret, 
            sum_for_trades=sum_for_trades)

@router.callback_query(F.data == "profile_menu")
async def profile_menu(callback: CallbackQuery, lang: str):
    """Обработка нажатия на кнопку 'Мой профиль'"""

    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    is_subscriber = await db.is_subscriber(user_id)
    is_wait_sub_confirmation = await db.is_wait_sub_confirmation(user_id)
    
    text_config = await get_config_lang(lang)
    user = await db.get_user_by_username_or_id(user_id)

    if is_subscriber and not is_wait_sub_confirmation: # sub true & wait false
        reply_markup = (await profile_menu_kb(user_id, lang)).as_markup()
        text = await _format_profile_text_by_template(user, text_config, "profile_menu")
    elif is_subscriber and is_wait_sub_confirmation: # sub true & wait true
        reply_markup = (await profile_menu_wait_sub_confirmation_kb_with_subscription(user_id, lang)).as_markup()
        text = await _format_profile_text_by_template(user, text_config, "profile_menu")
    elif not is_subscriber and is_wait_sub_confirmation: # sub false & wait true
        reply_markup = (await profile_menu_wait_sub_confirmation_kb_without_subscription(user_id, lang)).as_markup()
        text = text_config["profile_text"]["profile_menu_wait_sub_confirmation"]
    else: # sub false & wait false
        reply_markup = (await profile_menu_kb_without_subscription(user_id, lang)).as_markup()
        text = text_config["profile_text"]["profile_menu_without_subscription"]

    await safe_edit_message(callback, text, reply_markup=reply_markup)
    logger.info(f"Пользователь {user_id} ({username}) открыл меню 'Мой профиль'")

@router.callback_query(F.data == "statistics")
async def statistics(callback: CallbackQuery, lang: str):
    """Обработка нажатия на кнопку 'Статистика'"""

    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    
    text_config = await get_config_lang(lang)
    user = await db.get_user_by_username_or_id(user_id)

    text = await _format_profile_text_by_template(user, text_config, "profile_statistics")

    await safe_edit_message(
        callback, 
        text, 
        reply_markup=(await profile_statistics_kb(user_id, lang)).as_markup()
    )
    logger.info(f"Пользователь {user_id} ({username}) открыл меню 'Статистика'")

@router.callback_query(F.data == "settings_profile")
async def settings_profile(callback: CallbackQuery, lang: str):
    """Обработка нажатия на кнопку 'Настройки'"""

    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    
    text_config = await get_config_lang(lang)
    user = await db.get_user_by_username_or_id(user_id)

    text = await _format_profile_text_by_template(user, text_config, "profile_settings")
    await safe_edit_message(
        callback, 
        text, 
        reply_markup=(await profile_settings_kb(user_id, lang)).as_markup()
    )
    logger.info(f"Пользователь {user_id} ({username}) открыл меню 'Настройки'")

@router.callback_query(F.data == "profile_settings_api_key_secret")
async def profile_settings_api_key_secret(callback: CallbackQuery, state: FSMContext, lang: str):
    """Пользователь начинает изменение API key/secret."""
    user_id = callback.from_user.id
    text_config = await get_config_lang(lang)

    text = text_config["profile_text"]["profile_settings_api_key"]

    await state.set_state(ProfileStates.edit_api_key)
    await callback.answer()
    await safe_edit_message(
        callback,
        text,
        reply_markup=(await back_to_profile_settings_kb(user_id, lang)).as_markup(),
    )


@router.message(ProfileStates.edit_api_key, F.text)
async def process_profile_edit_api_key(message: Message, state: FSMContext, lang: str):
    """Пользователь вводит API key, затем просим API secret."""
    text_config = await get_config_lang(lang)
    api_key = message.text.strip()

    text = text_config["profile_text"]["profile_settings_api_secret"]

    await state.update_data(new_api_key=api_key)
    await state.set_state(ProfileStates.edit_api_secret)
    await message.answer(
        text,
        reply_markup=(await back_to_profile_settings_kb(message.from_user.id, lang)).as_markup(),
    )


@router.message(ProfileStates.edit_api_secret, F.text)
async def process_profile_edit_api_secret(message: Message, state: FSMContext, lang: str):
    """Пользователь вводит API secret, сохраняем пару key/secret."""
    user_id = message.from_user.id
    username = message.from_user.username or ""
    text_config = await get_config_lang(lang)

    data = await state.get_data()
    api_key = data.get("new_api_key", "")
    api_secret = message.text.strip()

    try:
        await db.update_api_key(user_id, api_key)
        await db.update_api_secret(user_id, api_secret)
    except (ValidationError, UsersRepositoryError) as e:
        await message.answer(f"Не удалось обновить API key/secret: {e}")
        return

    user = await db.get_user_by_username_or_id(user_id)
    if user is None:
        await message.answer(text_config["admin_text"]["error_user_not_found"])
        await state.clear()
        return

    await state.clear()
    await message.answer(
        await _format_profile_text_by_template(user, text_config, "profile_settings"),
        reply_markup=(await profile_settings_kb(user_id, lang)).as_markup(),
    )
    logger.info(f"Пользователь {user_id} ({username}) обновил API key/secret")


@router.callback_query(F.data == "profile_settings_sum_for_trades")
async def profile_settings_sum_for_trades(callback: CallbackQuery, state: FSMContext, lang: str):
    """Пользователь начинает изменение суммы сделки."""
    user_id = callback.from_user.id
    text_config = await get_config_lang(lang)

    text = text_config["profile_text"]["profile_settings_sum_for_trades"]

    await state.set_state(ProfileStates.edit_sum_for_trades)
    await callback.answer()
    await safe_edit_message(
        callback,
        text,
        reply_markup=(await back_to_profile_settings_kb(user_id, lang)).as_markup(),
    )


@router.message(ProfileStates.edit_sum_for_trades, F.text)
async def process_profile_edit_sum_for_trades(message: Message, state: FSMContext, lang: str):
    """Пользователь вводит новую сумму сделки."""
    user_id = message.from_user.id
    username = message.from_user.username or ""
    text_config = await get_config_lang(lang)
    sum_for_trades = message.text.strip()

    try:
        await db.update_sum_for_trades(user_id, sum_for_trades)
    except (ValidationError, UsersRepositoryError) as e:
        await message.answer(f"Не удалось обновить сумму сделки: {e}")
        return

    user = await db.get_user_by_username_or_id(user_id)
    if user is None:
        await message.answer(text_config["admin_text"]["error_user_not_found"])
        await state.clear()
        return

    await state.clear()
    await message.answer(
        await _format_profile_text_by_template(user, text_config, "profile_settings"),
        reply_markup=(await profile_settings_kb(user_id, lang)).as_markup(),
    )
    logger.info(f"Пользователь {user_id} ({username}) обновил сумму сделки")