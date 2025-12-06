from celery_app.celery_config import celery_app
from logger_config import setup_logger
import sys
from pathlib import Path
from celery_app.utils import setup_project_path

logger = setup_logger(__name__)

@celery_app.task(
    name='short_3_limit',
    bind=True,
    max_retries=3,
    default_retry_delay=5
)
def short_3_limit(self, symbol: str):
    """
    Запускает алгоритм short для символа
    
    Args:
        self: Объект задачи (обязателен при bind=True)
        symbol: Символ торговой пары (например, "BTCUSDT")
    """
    setup_project_path()  # Добавляем корневую директорию проекта в PYTHONPATH
    
    logger.info(f"🔄 Выполняется задача short_3_limit для символа {symbol}")
    
    from bybit_logic.api_algorithms.short_bu_ts_limit import start_trading
    start_trading(symbol)
    
    logger.info(f"✅ Задача short_3_limit для символа {symbol} завершена")
    return {"status": "completed", "symbol": symbol}