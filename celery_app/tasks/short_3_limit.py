from celery_app.celery_config import celery_app
from logger_config import setup_logger
from celery_app.utils import setup_project_path
from celery_app.config import REDIS_URL

logger = setup_logger(__name__)

@celery_app.task(
    name='short_3_limit',
    bind=True,
    queue='trade_user',
    max_retries=3,
    default_retry_delay=5
)
def short_3_limit(
    self,
    symbol: str,
    tg_id: int,
    name: str,
    api_key: str,
    api_secret: str,
    sum_for_trades: float,
):
    """
    Запускает алгоритм short для символа
    
    Args:
        self: Объект задачи (обязателен при bind=True)
        symbol: Символ торговой пары (например, "BTCUSDT")
    """
    setup_project_path()  # Добавляем корневую директорию проекта в PYTHONPATH

    lock = None
    lock_key = f"trade:{tg_id}:{symbol.upper()}"
    try:
        import redis
        redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        lock = redis_client.lock(lock_key, timeout=60 * 60 * 4, blocking=False)
        if not lock.acquire(blocking=False):
            logger.warning("⏭️ Дубликат задачи отфильтрован: %s", lock_key)
            return {"status": "skipped_duplicate", "symbol": symbol, "tg_id": tg_id}
    except Exception as lock_err:
        logger.warning("Не удалось установить redis-lock (%s), продолжаем без lock", lock_err)

    logger.info("🔄 Выполняется задача short_3_limit: symbol=%s tg_id=%s", symbol, tg_id)

    from bybit_logic.api_algorithms.short_bu_ts_limit_multiuser import start_trading
    try:
        start_trading(
            symbol=symbol,
            tg_id=tg_id,
            name=name,
            api_key=api_key,
            api_secret=api_secret,
            sum_for_trades=float(sum_for_trades),
        )
    finally:
        if lock is not None:
            try:
                lock.release()
            except Exception:
                pass

    logger.info("✅ Задача short_3_limit завершена: symbol=%s tg_id=%s", symbol, tg_id)
    return {"status": "completed", "symbol": symbol, "tg_id": tg_id}
    