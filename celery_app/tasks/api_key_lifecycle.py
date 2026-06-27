from celery_app.celery_config import celery_app
from logger_config import setup_logger

logger = setup_logger(__name__)


@celery_app.task(name="check_api_key_lifecycle", bind=True, max_retries=1, default_retry_delay=300)
def check_api_key_lifecycle_task(self):
    try:
        from celery_app.api_key_lifecycle_service import run_api_key_lifecycle_check

        return run_api_key_lifecycle_check()
    except Exception as exc:
        logger.error("check_api_key_lifecycle failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc) from exc
