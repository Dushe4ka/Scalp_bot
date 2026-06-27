"""Напоминания об истечении API-ключа Bybit: за 3/1 день и в день истечения."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from bot.languages.en import EN_CONFIGURATION
from bot.languages.ru import RU_CONFIGURATION
from database.api_key_lifecycle_repository import (
    _NOTIFY_API_1D,
    _NOTIFY_API_3D,
    _NOTIFY_API_EXPIRED,
    api_key_lifecycle_db,
)
from logger_config import setup_logger

logger = setup_logger(__name__)
_MOSCOW = ZoneInfo("Europe/Moscow")


def _config_for_language(language: str | None) -> dict[str, Any]:
    lang = (language or "ru").strip().lower()
    if lang == "en":
        return EN_CONFIGURATION
    return RU_CONFIGURATION


def _parse_expired_at(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str) and raw.strip():
        text = raw.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw.strip(), fmt)
            except ValueError:
                continue
    logger.warning("Не удалось распарсить api_key_expired_at: %r", raw)
    return None


def _same_expiry_moment(stored: Any, current: datetime) -> bool:
    parsed = _parse_expired_at(stored)
    if parsed is None:
        return False
    a = parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    b = current.replace(tzinfo=None) if current.tzinfo else current
    return abs((a - b).total_seconds()) < 120


def _days_until_expiry(expired_at: datetime, now: datetime) -> int:
    end_local = expired_at.astimezone(_MOSCOW) if expired_at.tzinfo else expired_at.replace(tzinfo=_MOSCOW)
    now_local = now.astimezone(_MOSCOW)
    return (end_local.date() - now_local.date()).days


def _format_expiry_date(expired_at: datetime) -> str:
    end_local = expired_at.astimezone(_MOSCOW) if expired_at.tzinfo else expired_at.replace(tzinfo=_MOSCOW)
    return end_local.strftime("%d.%m.%Y")


def _message_for_user(language: str | None, key: str, *, expired_at: datetime) -> str:
    cfg = _config_for_language(language)
    template = cfg.get("profile_text", {}).get(key)
    if not template:
        return key
    return template.format(expiry_date=_format_expiry_date(expired_at))


def _send_user_notification(tg_id: int, text: str) -> bool:
    from celery_app.tasks.notifications import send_notification_to_user_task

    try:
        result = send_notification_to_user_task.apply(args=[int(tg_id), text])
        payload = result.result if result else {}
        return bool(payload.get("ok"))
    except Exception as e:
        logger.error("Не удалось отправить уведомление API-ключа tg_id=%s: %s", tg_id, e, exc_info=True)
        return False


def run_api_key_lifecycle_check(now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(_MOSCOW)
    stats = {
        "checked": 0,
        "reminder_3d": 0,
        "reminder_1d": 0,
        "expired": 0,
        "skipped": 0,
        "errors": 0,
    }

    users = api_key_lifecycle_db.list_users_with_api_key_expiry()
    for user in users:
        stats["checked"] += 1
        tg_id = int(user["tg_id"])
        bybit = user.get("bybit_data") or {}
        expired_at = _parse_expired_at(bybit.get("api_key_expired_at"))
        if expired_at is None:
            stats["skipped"] += 1
            continue

        language = user.get("language")
        days_left = _days_until_expiry(expired_at, now)

        try:
            if days_left == 0 and not _same_expiry_moment(bybit.get(_NOTIFY_API_EXPIRED), expired_at):
                text = _message_for_user(language, "api_key_expired_today", expired_at=expired_at)
                if _send_user_notification(tg_id, text):
                    api_key_lifecycle_db.mark_notification_sent(tg_id, _NOTIFY_API_EXPIRED, expired_at)
                    stats["expired"] += 1
                continue

            if days_left == 3 and not _same_expiry_moment(bybit.get(_NOTIFY_API_3D), expired_at):
                text = _message_for_user(language, "api_key_reminder_3d", expired_at=expired_at)
                if _send_user_notification(tg_id, text):
                    api_key_lifecycle_db.mark_notification_sent(tg_id, _NOTIFY_API_3D, expired_at)
                    stats["reminder_3d"] += 1
                continue

            if days_left == 1 and not _same_expiry_moment(bybit.get(_NOTIFY_API_1D), expired_at):
                text = _message_for_user(language, "api_key_reminder_1d", expired_at=expired_at)
                if _send_user_notification(tg_id, text):
                    api_key_lifecycle_db.mark_notification_sent(tg_id, _NOTIFY_API_1D, expired_at)
                    stats["reminder_1d"] += 1
                continue

        except Exception as e:
            stats["errors"] += 1
            logger.error("Ошибка проверки API-ключа tg_id=%s: %s", tg_id, e, exc_info=True)

    logger.info(
        "Проверка API-ключей завершена: checked=%s reminder_3d=%s reminder_1d=%s expired=%s skipped=%s errors=%s",
        stats["checked"],
        stats["reminder_3d"],
        stats["reminder_1d"],
        stats["expired"],
        stats["skipped"],
        stats["errors"],
    )
    return stats
