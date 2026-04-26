from celery_app.celery_config import celery_app
from celery_app.config import REDIS_URL
from celery_app.utils import setup_project_path
from logger_config import setup_logger

logger = setup_logger(__name__)


@celery_app.task(
    name="hedge_long_short_bu_ts",
    bind=True,
    queue="trade_user",
    max_retries=3,
    default_retry_delay=5,
)
def hedge_long_short_bu_ts_task(self, symbol: str):
    """
    Немультюзерный hedge long+short по одному аккаунту (ключи из config / session).
    """
    setup_project_path()

    lock = None
    lock_key = f"trade:hedge:{symbol.upper()}"
    try:
        import redis

        redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        lock = redis_client.lock(lock_key, timeout=60 * 60 * 4, blocking=False)
        if not lock.acquire(blocking=False):
            logger.warning("Дубликат hedge задачи отфильтрован: %s", lock_key)
            return {"status": "skipped_duplicate", "symbol": symbol}
    except Exception as lock_err:
        logger.warning("Redis-lock (%s) недоступен, продолжаем без lock: %s", lock_key, lock_err)

    logger.info("Запуск hedge_long_short_bu_ts: symbol=%s", symbol)

    from bybit_logic.api_algorithms.hedge_long_short_bu_ts import start_trading

    try:
        start_trading(symbol=symbol)
    finally:
        if lock is not None:
            try:
                lock.release()
            except Exception:
                pass

    logger.info("hedge_long_short_bu_ts завершён: symbol=%s", symbol)
    return {"status": "completed", "symbol": symbol}
