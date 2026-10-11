from celery_app.celery_config import celery_app
from logger_config import setup_logger

logger = setup_logger(__name__)

_LOCK_KEY = "watchdog:run_lock"


@celery_app.task(name="check_active_trades", queue="watchdog", ignore_result=True)
def check_active_trades_task():
    """Сторож сделок (см. celery_app/trade_watchdog.py). Запуски не накладываются друг на друга."""
    import redis

    from celery_app.config import REDIS_URL
    from celery_app.trade_watchdog import WATCHDOG_INTERVAL_SEC, build_default_watchdog

    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    if not client.set(_LOCK_KEY, "1", nx=True, ex=int(WATCHDOG_INTERVAL_SEC * 5)):
        logger.info("check_active_trades: предыдущий проход ещё идёт — пропуск")
        return None
    try:
        summary = build_default_watchdog().run_once()
        if summary.get("checked"):
            logger.info("check_active_trades: %s", summary)
        return summary
    except Exception as exc:
        logger.error("check_active_trades failed: %s", exc, exc_info=True)
        return None
    finally:
        client.delete(_LOCK_KEY)
