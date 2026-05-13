import os

from celery_app.celery_config import celery_app
from celery_app.config import REDIS_URL
from celery_app.utils import setup_project_path
from logger_config import setup_logger

logger = setup_logger(__name__)


def get_nomulti_short_3_params() -> tuple[int, str, str, str, float]:
    """
    tg_id, name, api_key, api_secret, sum_for_trades — как у multi short_3_limit,
    но из тех же .env, что и остальной nomulti: TG_ID, TG_NAME, USDT_AMOUNT, ключи Bybit.
    """
    from config import ADMIN_CHAT_ID, USE_DEMO
    from bybit_logic.config import API_KEY, API_SECRET, DEMO_API_KEY, DEMO_API_SECRET

    if USE_DEMO:
        api_key = (DEMO_API_KEY or "").strip()
        api_secret = (DEMO_API_SECRET or "").strip()
    else:
        api_key = (API_KEY or "").strip()
        api_secret = (API_SECRET or "").strip()

    tg_id: int | None = None
    for raw in (os.getenv("TG_ID"), ADMIN_CHAT_ID):
        if raw is None:
            continue
        s = str(raw).strip()
        if not s:
            continue
        try:
            tg_id = int(s)
            break
        except ValueError:
            continue
    if tg_id is None:
        raise ValueError(
            "Задайте TG_ID в .env (telegram id владельца), либо ADMIN_CHAT_ID для истории и уведомлений"
        )
    name = (os.getenv("TG_NAME") or "nomulti").strip() or "nomulti"

    sum_raw = os.getenv("SHORT_BU_TS_LIMIT_USDT_AMOUNT") or os.getenv("USDT_AMOUNT")
    if sum_raw is None or str(sum_raw).strip() == "":
        raise ValueError(
            "Задайте USDT_AMOUNT в .env (или SHORT_BU_TS_LIMIT_USDT_AMOUNT) — сумма в USDT для short_3_limit"
        )
    sum_for_trades = float(sum_raw)

    if not api_key or not api_secret:
        raise ValueError("В .env не заданы API_KEY/API_SECRET (или DEMO_* при USE_DEMO=true)")
    if sum_for_trades <= 0:
        raise ValueError("Сумма для торговли должна быть > 0")

    return tg_id, name, api_key, api_secret, sum_for_trades


@celery_app.task(
    name="nomulti_short_3_limit",
    bind=True,
    queue="trade_user",
    max_retries=3,
    default_retry_delay=5,
)
def nomulti_short_3_limit_task(self, symbol: str):
    """Один short_3_limit (алгоритм short_bu_ts_limit_multiuser) по ключам из .env."""
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

    tg_id, name, api_key, api_secret, sum_for_trades = get_nomulti_short_3_params()
    logger.info(
        "Запуск nomulti_short_3_limit: symbol=%s tg_id=%s sum_for_trades=%s",
        symbol,
        tg_id,
        sum_for_trades,
    )

    from bybit_logic.api_algorithms.short_bu_ts_limit_multiuser import start_trading

    try:
        start_trading(
            symbol=symbol,
            tg_id=tg_id,
            name=name,
            api_key=api_key,
            api_secret=api_secret,
            sum_for_trades=sum_for_trades,
        )
    finally:
        if lock is not None:
            try:
                lock.release()
            except Exception:
                pass

    logger.info("nomulti_short_3_limit завершён: symbol=%s tg_id=%s", symbol, tg_id)
    return {"status": "completed", "symbol": symbol, "tg_id": tg_id}
