from celery_app.celery_config import celery_app
from logger_config import setup_logger
from celery_app.utils import setup_project_path

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

    logger.info("🔄 Выполняется задача short_3_limit: symbol=%s tg_id=%s", symbol, tg_id)

    from bybit_logic.api_algorithms.short_bu_ts_limit_multiuser import start_trading

    trade_id = start_trading(
        symbol=symbol,
        tg_id=tg_id,
        name=name,
        api_key=api_key,
        api_secret=api_secret,
        sum_for_trades=float(sum_for_trades),
    )

    logger.info(
        "✅ Задача short_3_limit поставлена в async-движок: symbol=%s tg_id=%s trade_id=%s",
        symbol,
        tg_id,
        trade_id,
    )
    return {
        "status": "submitted",
        "symbol": symbol,
        "tg_id": tg_id,
        "trade_id": trade_id,
    }
    