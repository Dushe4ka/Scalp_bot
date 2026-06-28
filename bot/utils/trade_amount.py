"""Лимиты и подсказки по сумме сделки в профиле."""

from typing import Any

from bot.languages._lang_func import get_config_lang
from bot.utils.helpers import extract_user_api_credentials, get_recommended_trade_amount
from config import RECOMMENDED_TRADE_AMOUNT_PERCENT
from database.app_settings_repository import app_settings_db


def format_trade_amount_percent(lang: str) -> str:
    value = float(RECOMMENDED_TRADE_AMOUNT_PERCENT)
    text = f"{value:g}"
    if lang == "ru":
        return text.replace(".", ",")
    return text


async def user_has_unlimited_trade_amount(tg_id: int) -> bool:
    return await app_settings_db.is_unlimited_trade_amount(tg_id)


async def resolve_trade_amount_limit(
    user: dict[str, Any],
    tg_id: int,
) -> tuple[float | None, bool, str | None]:
    """
  Возвращает (лимит в USDT, без_ограничений, код_ошибки).
  код_ошибки: api_missing | balance_zero | fetch_error | None
    """
    api_key, api_secret = extract_user_api_credentials(user)
    if not api_key or not api_secret:
        return None, False, "api_missing"

    amount = await get_recommended_trade_amount(user)
    if amount is None:
        return None, False, "fetch_error"
    if amount <= 0:
        return None, False, "balance_zero"

    unlimited = await user_has_unlimited_trade_amount(tg_id)
    return float(amount), unlimited, None


async def build_sum_for_trades_prompt(
    lang: str,
    tg_id: int,
    user: dict[str, Any],
) -> tuple[str, float | None, bool]:
    """Текст подсказки при вводе суммы сделки."""
    text_config = await get_config_lang(lang)
    profile_text = text_config["profile_text"]
    amount, unlimited, error_key = await resolve_trade_amount_limit(user, tg_id)
    percent = format_trade_amount_percent(lang)

    if error_key == "api_missing":
        return profile_text["profile_settings_sum_for_trades_api_required"], None, False
    if error_key == "balance_zero":
        return profile_text["profile_settings_sum_for_trades_balance_zero"], None, False
    if error_key == "fetch_error" or amount is None:
        return profile_text["profile_settings_sum_for_trades_fallback"], None, unlimited

    if unlimited:
        text = profile_text["profile_settings_sum_for_trades"].format(
            recommended_usdt=f"{amount:.2f}",
        )
    else:
        text = profile_text["profile_settings_sum_for_trades_limited"].format(
            max_usdt=f"{amount:.2f}",
            percent=percent,
        )
    return text, amount, unlimited
