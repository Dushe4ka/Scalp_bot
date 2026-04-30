from celery_app.celery_config import celery_app
from bot.utils.helpers import send_to_subscribers_sync
from logger_config import setup_logger
from config import TELEGRAM_BOT_TOKEN
import requests

logger = setup_logger(__name__)

@celery_app.task(
    name='send_notification',
    bind=True,
    max_retries=2,
    default_retry_delay=10
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
        result = send_to_subscribers_sync(text)
        logger.info(f"Уведомление отправлено: {result['sent']}/{result['total']} подписчиков")
        return result
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления: {e}")
        # Повторяем попытку при ошибке
        raise self.retry(exc=e)


@celery_app.task(
    name='send_notification_to_user',
    bind=True,
    max_retries=2,
    default_retry_delay=10
)
def send_notification_to_user_task(self, tg_id: int, text: str):
    """
    Отправка уведомления конкретному пользователю в Telegram.
    """
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
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
                tg_id, attempt, max_attempts, e
            )
    raise self.retry(exc=last_error)
