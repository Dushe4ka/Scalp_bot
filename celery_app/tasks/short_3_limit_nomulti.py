import os

from celery_app.celery_config import celery_app
from celery_app.config import REDIS_URL
from celery_app.utils import setup_project_path
from logger_config import setup_logger

logger = setup_logger(__name__)


def ensure_nomulti_short_bu_ts_env() -> None:
    """
    Проверка .env перед nomulti_short_3_limit: те же поля, что реально читает short_bu_ts_limit
    (ключи Bybit и сумма). Символ приходит только с эндпоинта.
    """
    from config import USE_DEMO
    from bybit_logic.config import API_KEY, API_SECRET, DEMO_API_KEY, DEMO_API_SECRET

    if USE_DEMO:
        api_key = (DEMO_API_KEY or "").strip()
        api_secret = (DEMO_API_SECRET or "").strip()
    else:
        api_key = (API_KEY or "").strip()
        api_secret = (API_SECRET or "").strip()

    if not api_key or not api_secret:
        raise ValueError(
            "В .env не заданы API_KEY/API_SECRET (или DEMO_API_KEY/DEMO_API_SECRET при USE_DEMO=true)"
        )

    sum_raw = os.getenv("SHORT_BU_TS_LIMIT_USDT_AMOUNT") or os.getenv("USDT_AMOUNT")
    if sum_raw is None or str(sum_raw).strip() == "":
        raise ValueError(
            "Задайте SHORT_BU_TS_LIMIT_USDT_AMOUNT или USDT_AMOUNT в .env — сумма в USDT для алгоритма"
        )
    try:
        s = float(sum_raw)
    except ValueError as e:
        raise ValueError(
            "SHORT_BU_TS_LIMIT_USDT_AMOUNT / USDT_AMOUNT должно быть числом"
        ) from e
    if s <= 0:
        raise ValueError("Сумма для торговли должна быть > 0")


@celery_app.task(
    name="nomulti_short_3_limit",
    bind=True,
    queue="trade_user",
    max_retries=3,
    default_retry_delay=5,
)
def nomulti_short_3_limit_task(self, symbol: str):
    """short_bu_ts_limit по .env; символ из тела запроса; уведомления подписчикам из алгоритма."""
    setup_project_path()

    lock = None
    lock_key = f"trade:nomulti_short_3:{symbol.upper()}"
    try:
        import redis

        redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        lock = redis_client.lock(lock_key, timeout=60 * 60 * 4, blocking=False)
        if not lock.acquire(blocking=False):
            logger.warning("Дубликат nomulti_short_3_limit отфильтрован: %s", lock_key)
            return {"status": "skipped_duplicate", "symbol": symbol}
    except Exception as lock_err:
        logger.warning("Redis-lock (%s) недоступен, продолжаем без lock: %s", lock_key, lock_err)

    ensure_nomulti_short_bu_ts_env()
    sum_note = os.getenv("SHORT_BU_TS_LIMIT_USDT_AMOUNT") or os.getenv("USDT_AMOUNT")
    logger.info(
        "Запуск nomulti_short_3_limit: symbol=%s sum_env=%s (short_bu_ts_limit)",
        symbol,
        sum_note,
    )

    from bybit_logic.api_algorithms.short_bu_ts_limit_engine import start_trading_nomulti

    trade_id = None
    try:
        trade_id = start_trading_nomulti(symbol=symbol)
        logger.info("nomulti_short_3_limit trade_id=%s symbol=%s", trade_id, symbol)
    finally:
        if lock is not None:
            try:
                lock.release()
            except Exception:
                pass

    logger.info("nomulti_short_3_limit завершён: symbol=%s trade_id=%s", symbol, trade_id)
    return {"status": "submitted", "symbol": symbol, "trade_id": trade_id}
