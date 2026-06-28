"""Общая логика отображения личного кабинета (кнопка и команда /profile)."""
from __future__ import annotations

from typing import Any

from aiogram.types import InlineKeyboardMarkup

from bot.keyboards.inline_kb import (
    profile_menu_kb,
    profile_menu_kb_without_subscription,
    profile_menu_wait_sub_confirmation_kb_with_subscription,
    profile_menu_wait_sub_confirmation_kb_without_subscription,
)
from bot.languages._lang_func import get_config_lang
from bot.utils.api_key_expiry import refresh_user_api_key_expiry, build_api_key_expiry_line
from bot.utils.misc import _format_dt
from database.users_repository import db


async def _format_profile_text_by_template(user: dict[str, Any], text_config: dict[str, Any]) -> str:
    template = text_config.get("profile_text", {}).get("profile_menu")
    subscription_data = user.get("subscription_data") or {}
    bybit_data = user.get("bybit_data") or {}

    payment_date = _format_dt(subscription_data.get("payment_date"))
    subscription_type = subscription_data.get("subscription_type")
    sum_for_trades = bybit_data.get("sum_for_trades")
    api_key = "✅" if bybit_data.get("api_key") else "❌"
    api_key_expiry_line = build_api_key_expiry_line(
        bybit_data,
        text_config["profile_text"]["profile_api_key_expiry"],
    )

    return template.format(
        payment_date=payment_date,
        subscription_type=subscription_type,
        sum_for_trades=sum_for_trades,
        api_key=api_key,
        api_key_expiry_line=api_key_expiry_line,
    )


async def build_profile_menu_view(user_id: int, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    """Возвращает текст и клавиатуру личного кабинета."""
    text_config = await get_config_lang(lang)
    is_subscriber = await db.is_subscriber(user_id)
    is_wait_sub_confirmation = await db.is_wait_sub_confirmation(user_id)

    user = await db.get_user_by_username_or_id(user_id)
    if user and user.get("bybit_data", {}).get("api_key") and user.get("bybit_data", {}).get("api_secret"):
        user = await refresh_user_api_key_expiry(user)

    if is_subscriber and not is_wait_sub_confirmation:
        text = await _format_profile_text_by_template(user, text_config)
        markup = (await profile_menu_kb(user_id, lang)).as_markup()
    elif is_subscriber and is_wait_sub_confirmation:
        text = await _format_profile_text_by_template(user, text_config)
        markup = (await profile_menu_wait_sub_confirmation_kb_with_subscription(user_id, lang)).as_markup()
    elif not is_subscriber and is_wait_sub_confirmation:
        text = text_config["profile_text"]["profile_menu_wait_sub_confirmation"]
        markup = (await profile_menu_wait_sub_confirmation_kb_without_subscription(user_id, lang)).as_markup()
    else:
        text = text_config["profile_text"]["profile_menu_without_subscription"]
        markup = (await profile_menu_kb_without_subscription(user_id, lang)).as_markup()

    return text, markup
