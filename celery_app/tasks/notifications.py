import os

import requests

from celery_app.celery_config import celery_app
from bot.utils.helpers import send_to_subscribers_sync
from config import TELEGRAM_BOT_TOKEN
from logger_config import setup_logger

logger = setup_logger(__name__)


def _user_notification_bot_token() -> str | None:
    """
    Токен бота для личных уведомлений multiuser (send_notification_to_user).
    Приоритет: CELERY_TRADING_BOT_TOKEN → CELERY_SUBSCRIBERS_BOT_TOKEN → TELEGRAM_BOT_TOKEN → TEST_TELEGRAM_BOT_TOKEN.
    """
    from bot.config import TEST_TELEGRAM_BOT_TOKEN

    raw = (
        os.getenv("CELERY_TRADING_BOT_TOKEN")
        or os.getenv("CELERY_SUBSCRIBERS_BOT_TOKEN")
        or TELEGRAM_BOT_TOKEN
        or TEST_TELEGRAM_BOT_TOKEN
        or ""
    )
    return str(raw).strip() or None


def _subscriber_broadcast_bot_token() -> str | None:
    """
    Токен бота для рассылки по коллекции subscribers (Mongo).
    Если подписчики жмут /subscribe в nomulti-боте, сюда нужен его токен:
    CELERY_SUBSCRIBERS_BOT_TOKEN в .env (иначе берётся TELEGRAM_BOT_TOKEN из config).
    """
    raw = (os.getenv("CELERY_SUBSCRIBERS_BOT_TOKEN") or "").strip()
    if raw:
        return raw
    return (TELEGRAM_BOT_TOKEN or "").strip() or None


def _admin_target_chat_ids() -> list[int]:
    """Уникальные chat_id для служебных уведомлений (ADMIN_CHAT_ID + ADMIN_IDS)."""
    from config import ADMIN_CHAT_ID, ADMIN_IDS

    out: list[int] = []
    seen: set[int] = set()
    if ADMIN_CHAT_ID:
        s = str(ADMIN_CHAT_ID).strip()
        if s:
            try:
                v = int(s)
                if v not in seen:
                    seen.add(v)
                    out.append(v)
            except ValueError:
                pass
    for aid in sorted(ADMIN_IDS):
        if aid not in seen:
            seen.add(aid)
            out.append(aid)
    return out


@celery_app.task(
    name="send_notification",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
)
def send_notification_task(self, text: str):
    """
    Отправка уведомления подписчикам через Celery
    Не блокирует основной алгоритм торговли

    Args:
        self: Объект задачи (обязателен при bind=True)
        text: Текст уведомления
    """
    try:
        token = _subscriber_broadcast_bot_token()
        result = send_to_subscribers_sync(text, bot_token=token)
        logger.info("Уведомление отправлено: %s/%s подписчиков", result["sent"], result["total"])
        return result
    except Exception as e:
        logger.error("Ошибка отправки уведомления: %s", e)
        raise self.retry(exc=e) from e


@celery_app.task(
    name="send_notification_to_admins",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
)
def send_notification_to_admins_task(self, text: str):
    """
    Служебное уведомление только админам (ADMIN_CHAT_ID и ADMIN_IDS).
    """
    token = (TELEGRAM_BOT_TOKEN or "").strip()
    if not token:
        logger.error("send_notification_to_admins_task: TELEGRAM_BOT_TOKEN не задан")
        return {"ok": False, "error": "missing_bot_token"}
    targets = _admin_target_chat_ids()
    if not targets:
        logger.warning(
            "send_notification_to_admins_task: нет ADMIN_CHAT_ID и ADMIN_IDS — некуда отправить"
        )
        return {"ok": False, "sent": 0, "targets": 0}
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    sent = 0
    for chat_id in targets:
        try:
            response = requests.post(
                api_url,
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
            if not payload.get("ok"):
                raise RuntimeError(payload.get("description", "Unknown Telegram error"))
            sent += 1
            logger.info("Админ-уведомление отправлено chat_id=%s", chat_id)
        except Exception as e:
            logger.error("Ошибка админ-уведомления chat_id=%s: %s", chat_id, e)
    return {"ok": True, "sent": sent, "targets": len(targets)}


@celery_app.task(
    name="send_notification_to_user",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
)
def send_notification_to_user_task(self, tg_id: int, text: str):
    """
    Отправка уведомления конкретному пользователю в Telegram.
    """
    token = _user_notification_bot_token()
    if not token:
        logger.error("send_notification_to_user_task: не задан токен бота")
        return {"ok": False, "error": "missing_bot_token", "tg_id": tg_id}
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    max_attempts = 3
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.post(
                api_url,
                json={
                    "chat_id": int(tg_id),
                    "text": text,
                    "parse_mode": "HTML",
                },
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
            if not payload.get("ok"):
                raise RuntimeError(payload.get("description", "Unknown Telegram error"))
            logger.info("Уведомление отправлено tg_id=%s (попытка %s)", tg_id, attempt)
            return {"ok": True, "tg_id": tg_id}
        except Exception as e:
            last_error = e
            logger.error(
                "Ошибка отправки персонального уведомления tg_id=%s (попытка %s/%s): %s",
                tg_id,
                attempt,
                max_attempts,
                e,
            )
    raise self.retry(exc=last_error) from last_error
