from celery_app.celery_config import celery_app
from bot.utils.helpers import send_to_subscribers_sync
from logger_config import setup_logger

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
