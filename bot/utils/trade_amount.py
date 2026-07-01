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
    код_ошибки: api_missing | api_invalid | balance_zero | None
    """
    api_key, api_secret = extract_user_api_credentials(user)
    if not api_key or not api_secret:
        return None, False, "api_missing"

    amount = await get_recommended_trade_amount(user)
    if amount is None:
        return None, False, "api_invalid"
    if amount <= 0:
        return None, False, "balance_zero"

    unlimited = await user_has_unlimited_trade_amount(tg_id)
    return float(amount), unlimited, None


def user_with_api_credentials(
    user: dict[str, Any] | None,
    api_key: str,
    api_secret: str,
) -> dict[str, Any]:
    base = dict(user or {})
    bybit = dict(base.get("bybit_data") or {})
    bybit["api_key"] = api_key
    bybit["api_secret"] = api_secret
    return {**base, "bybit_data": bybit}


async def build_sum_for_trades_prompt(
    lang: str,
    tg_id: int,
    user: dict[str, Any],
) -> tuple[str, float | None, bool, str | None]:
    """Текст подсказки при вводе суммы сделки и код ошибки лимита (если есть)."""
    text_config = await get_config_lang(lang)
    profile_text = text_config["profile_text"]
    amount, unlimited, error_key = await resolve_trade_amount_limit(user, tg_id)
    percent = format_trade_amount_percent(lang)

    if error_key == "api_missing":
        return profile_text["profile_settings_sum_for_trades_api_required"], None, False, error_key
    if error_key == "api_invalid":
        return profile_text["profile_settings_api_invalid"], None, False, error_key
    if error_key == "balance_zero":
        return profile_text["profile_settings_sum_for_trades_balance_zero"], None, False, error_key
    if amount is None:
        return profile_text["profile_settings_api_invalid"], None, False, "api_invalid"

    if unlimited:
        text = profile_text["profile_settings_sum_for_trades"].format(
            recommended_usdt=f"{amount:.2f}",
        )
    else:
        text = profile_text["profile_settings_sum_for_trades_limited"].format(
            max_usdt=f"{amount:.2f}",
            percent=percent,
        )
    return text, amount, unlimited, None
