"""Периодическая проверка срока подписки (Celery Beat)."""
from __future__ import annotations

from celery_app.celery_config import celery_app
from celery_app.utils import setup_project_path
from logger_config import setup_logger

logger = setup_logger(__name__)


@celery_app.task(name="check_subscription_lifecycle", bind=True, max_retries=1, default_retry_delay=300)
def check_subscription_lifecycle_task(self):
    """
    Проверяет активные подписки:
    - за 3 дня до окончания — напоминание;
    - за 1 день — напоминание;
    - по истечении — отключение subscription и уведомление.
    """
    setup_project_path()
    try:
        from celery_app.subscription_lifecycle_service import run_subscription_lifecycle_check

        return run_subscription_lifecycle_check()
    except Exception as exc:
        logger.error("check_subscription_lifecycle failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc) from exc
