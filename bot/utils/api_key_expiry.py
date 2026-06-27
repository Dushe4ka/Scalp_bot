"""Синхронизация срока API-ключа пользователя с Bybit и форматирование для профиля."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from bybit_logic.bybit_func.api_key_info import fetch_api_key_expired_at
from bybit_logic.bybit_func.session import create_session
from bot.utils.helpers import extract_user_api_credentials
from config import USE_DEMO
from database.users_repository import db
from logger_config import setup_logger

logger = setup_logger(__name__)
_MOSCOW = ZoneInfo("Europe/Moscow")


def days_until_expiry(expired_at: datetime | None, now: datetime | None = None) -> int | None:
    if expired_at is None:
        return None
    now = now or datetime.now(_MOSCOW)
    end_local = expired_at.astimezone(_MOSCOW) if expired_at.tzinfo else expired_at.replace(tzinfo=_MOSCOW)
    now_local = now.astimezone(_MOSCOW)
    return (end_local.date() - now_local.date()).days


def format_expiry_date(expired_at: datetime) -> str:
    end_local = expired_at.astimezone(_MOSCOW) if expired_at.tzinfo else expired_at.replace(tzinfo=_MOSCOW)
    return end_local.strftime("%d.%m.%Y")


async def refresh_user_api_key_expiry(user: dict[str, Any]) -> dict[str, Any]:
    """
    Запрашивает Bybit и обновляет bybit_data.api_key_expired_at, если дата изменилась.
    Возвращает актуальный документ пользователя.
    """
    tg_id = int(user["tg_id"])
    api_key, api_secret = extract_user_api_credentials(user)
    if not api_key or not api_secret:
        return user

    try:
        session = create_session(use_demo=USE_DEMO, api_key=api_key, api_secret=api_secret)
        expired_at = await asyncio.to_thread(fetch_api_key_expired_at, session)
        await db.sync_api_key_expired_at(tg_id, expired_at)
        updated = await db.get_user(tg_id)
        return updated or user
    except Exception as e:
        logger.warning("Не удалось обновить срок API-ключа tg_id=%s: %s", tg_id, e)
        return user


def build_api_key_expiry_line(bybit_data: dict[str, Any], template: str) -> str:
    """Строка для профиля; пустая, если срок неизвестен или ключ не задан."""
    if not bybit_data.get("api_key") or not bybit_data.get("api_secret"):
        return ""

    expired_at = bybit_data.get("api_key_expired_at")
    if not isinstance(expired_at, datetime):
        return ""

    days_left = days_until_expiry(expired_at)
    if days_left is None:
        return ""

    return template.format(
        days_left=max(days_left, 0),
        expiry_date=format_expiry_date(expired_at),
    )
