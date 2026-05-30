"""Проверка срока подписки: напоминания за 3/1 день и отключение по истечении."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from bot.languages.en import EN_CONFIGURATION
from bot.languages.ru import RU_CONFIGURATION
from database.subscription_lifecycle_repository import (
    _NOTIFY_1D,
    _NOTIFY_3D,
    _NOTIFY_EXPIRED,
    subscription_lifecycle_db,
)
from logger_config import setup_logger

logger = setup_logger(__name__)

_MOSCOW = ZoneInfo("Europe/Moscow")


def _config_for_language(language: str | None) -> dict[str, Any]:
    lang = (language or "ru").strip().lower()
    if lang == "en":
        return EN_CONFIGURATION
    return RU_CONFIGURATION


def _parse_end_date(raw: Any) -> datetime | None:
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
    logger.warning("Не удалось распарсить end_subscription_date: %r", raw)
    return None


def _same_end_moment(stored: Any, current: datetime) -> bool:
    parsed = _parse_end_date(stored)
    if parsed is None:
        return False
    a = parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    b = current.replace(tzinfo=None) if current.tzinfo else current
    return abs((a - b).total_seconds()) < 120


def _days_until_end(end_date: datetime, now: datetime) -> int:
    end_local = end_date.astimezone(_MOSCOW) if end_date.tzinfo else end_date.replace(tzinfo=_MOSCOW)
    now_local = now.astimezone(_MOSCOW)
    return (end_local.date() - now_local.date()).days


def _format_end_date(end_date: datetime) -> str:
    end_local = end_date.astimezone(_MOSCOW) if end_date.tzinfo else end_date.replace(tzinfo=_MOSCOW)
    return end_local.strftime("%d.%m.%Y %H:%M")


def _message_for_user(language: str | None, key: str, *, end_date: datetime) -> str:
    cfg = _config_for_language(language)
    template = cfg.get("subscription_text", {}).get(key)
    if not template:
        return key
    return template.format(end_date=_format_end_date(end_date))


def _send_user_notification(tg_id: int, text: str) -> bool:
    from celery_app.tasks.notifications import send_notification_to_user_task

    try:
        result = send_notification_to_user_task.apply(args=[int(tg_id), text])
        payload = result.result if result else {}
        return bool(payload.get("ok"))
    except Exception as e:
        logger.error("Не удалось отправить уведомление tg_id=%s: %s", tg_id, e, exc_info=True)
        return False


def run_subscription_lifecycle_check(now: datetime | None = None) -> dict[str, int]:
    """
    Одна итерация проверки всех активных подписок.
    Возвращает счётчики для логов/мониторинга.
    """
    now = now or datetime.now(_MOSCOW)
    stats = {
        "checked": 0,
        "reminder_3d": 0,
        "reminder_1d": 0,
        "expired": 0,
        "skipped": 0,
        "errors": 0,
    }

    users = subscription_lifecycle_db.list_active_subscriptions()
    for user in users:
        stats["checked"] += 1
        tg_id = int(user["tg_id"])
        sub = user.get("subscription_data") or {}
        end_date = _parse_end_date(sub.get("end_subscription_date"))
        if end_date is None:
            stats["skipped"] += 1
            continue

        language = user.get("language")
        days_left = _days_until_end(end_date, now)

        try:
            if days_left <= 0:
                if not _same_end_moment(sub.get(_NOTIFY_EXPIRED), end_date):
                    text = _message_for_user(language, "subscription_expired", end_date=end_date)
                    if _send_user_notification(tg_id, text):
                        subscription_lifecycle_db.mark_notification_sent(
                            tg_id, _NOTIFY_EXPIRED, end_date
                        )
                subscription_lifecycle_db.deactivate_subscription(tg_id)
                stats["expired"] += 1
                logger.info(
                    "Подписка отключена (истекла): tg_id=%s end=%s",
                    tg_id,
                    _format_end_date(end_date),
                )
                continue

            if days_left == 3 and not _same_end_moment(sub.get(_NOTIFY_3D), end_date):
                text = _message_for_user(language, "subscription_reminder_3d", end_date=end_date)
                if _send_user_notification(tg_id, text):
                    subscription_lifecycle_db.mark_notification_sent(tg_id, _NOTIFY_3D, end_date)
                    stats["reminder_3d"] += 1
                continue

            if days_left == 1 and not _same_end_moment(sub.get(_NOTIFY_1D), end_date):
                text = _message_for_user(language, "subscription_reminder_1d", end_date=end_date)
                if _send_user_notification(tg_id, text):
                    subscription_lifecycle_db.mark_notification_sent(tg_id, _NOTIFY_1D, end_date)
                    stats["reminder_1d"] += 1
                continue

        except Exception as e:
            stats["errors"] += 1
            logger.error("Ошибка проверки подписки tg_id=%s: %s", tg_id, e, exc_info=True)

    logger.info(
        "Проверка подписок завершена: checked=%s reminder_3d=%s reminder_1d=%s expired=%s skipped=%s errors=%s",
        stats["checked"],
        stats["reminder_3d"],
        stats["reminder_1d"],
        stats["expired"],
        stats["skipped"],
        stats["errors"],
    )
    return stats
