"""Общая логика отображения личного кабинета (кнопка и команда /profile)."""
from __future__ import annotations

from typing import Any

from aiogram.types import InlineKeyboardMarkup

from bot.keyboards.inline_kb import (
    profile_menu_kb,
    profile_menu_kb_without_subscription,
    profile_menu_wait_sub_confirmation_kb,
)
from bot.languages._lang_func import get_config_lang
from bot.utils.api_key_expiry import refresh_user_api_key_expiry, build_api_key_expiry_line
from bot.utils.misc import _format_dt
from bot.utils.onboarding import build_onboarding_checklist
from database.users_repository import db


def _format_sum_display(bybit_data: dict[str, Any]) -> str:
    raw = bybit_data.get("sum_for_trades")
    if raw is None or str(raw).strip() in {"", "0", "0.0"}:
        return "не указана"
    return str(raw)


async def _build_profile_header(user: dict[str, Any] | None, text_config: dict[str, Any], template_key: str) -> str:
    user = user or {}
    subscription_data = user.get("subscription_data") or {}
    bybit_data = user.get("bybit_data") or {}
    checklist = build_onboarding_checklist(
        user,
        text_config,
        is_subscriber=bool(subscription_data.get("subscription")),
        is_wait_confirm=bool(subscription_data.get("wait_sub_confirmation")),
    )

    if template_key == "profile_menu":
        api_key = "✅ указан" if bybit_data.get("api_key") else "❌ не указан"
        api_key_expiry_line = build_api_key_expiry_line(
            bybit_data,
            text_config["profile_text"]["profile_api_key_expiry"],
        )
        return text_config["profile_text"]["profile_menu"].format(
            payment_date=_format_dt(subscription_data.get("payment_date")),
            subscription_type=subscription_data.get("subscription_type") or "—",
            sum_for_trades=_format_sum_display(bybit_data),
            api_key=api_key,
            api_key_expiry_line=api_key_expiry_line,
            onboarding_checklist=checklist,
        )

    if template_key == "profile_menu_wait_sub_confirmation":
        return text_config["profile_text"]["profile_menu_wait_sub_confirmation"].format(
            onboarding_checklist=checklist,
        )

    return text_config["profile_text"]["profile_menu_without_subscription"].format(
        onboarding_checklist=checklist,
    )


async def build_profile_menu_view(user_id: int, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    """Возвращает текст и клавиатуру личного кабинета."""
    text_config = await get_config_lang(lang)
    is_subscriber = await db.is_subscriber(user_id)
    is_wait_sub_confirmation = await db.is_wait_sub_confirmation(user_id)

    user = await db.get_user_by_username_or_id(user_id)
    if user and user.get("bybit_data", {}).get("api_key") and user.get("bybit_data", {}).get("api_secret"):
        user = await refresh_user_api_key_expiry(user)

    if is_wait_sub_confirmation:
        text = await _build_profile_header(user, text_config, "profile_menu_wait_sub_confirmation")
        markup = (await profile_menu_wait_sub_confirmation_kb(user_id, lang)).as_markup()
    elif is_subscriber:
        text = await _build_profile_header(user, text_config, "profile_menu")
        markup = (await profile_menu_kb(user_id, lang)).as_markup()
    else:
        text = await _build_profile_header(user, text_config, "profile_menu_without_subscription")
        markup = (await profile_menu_kb_without_subscription(user_id, lang)).as_markup()

    return text, markup
