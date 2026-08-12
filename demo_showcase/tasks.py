"""Celery-задача demo-показа сделок для маркетинга.

Работает ТОЛЬКО в собственном изолированном воркер-процессе (очередь demo_showcase,
--concurrency=1). Форсирует demo-режим и подавляет запись в history_trades/statistics
для этого процесса — см. docs/superpowers/specs/2026-08-11-demo-showcase-trading-design.md.
"""
from __future__ import annotations

import os
from datetime import datetime

import redis

from celery_app.celery_config import celery_app
from celery_app.config import REDIS_URL
from demo_showcase.config import (
    DEMO_SHOWCASE_API_KEY,
    DEMO_SHOWCASE_API_SECRET,
    DEMO_SHOWCASE_NAME,
    DEMO_SHOWCASE_TG_ID,
    DEMO_SHOWCASE_USDT_AMOUNT,
)
from demo_showcase.repository import NoOpHistoryTradesDb, demo_showcase_trades_db
from logger_config import setup_logger

logger = setup_logger(__name__)

_LOCK_TTL_SECONDS = 60 * 60 * 4


def _force_demo_isolation() -> None:
    """
    Форсирует demo-режим и подавляет запись в history_trades для ЭТОГО процесса.

    Патчит ДВЕ ссылки на history_trades_db: атрибут модуля database.history_trades_repository
    (для кода, который импортирует модуль целиком) И одноимённое имя, уже связанное внутри
    short_bu_ts_limit_engine через `from database.history_trades_repository import history_trades_db`
    (это байндинг имени, а не чтение атрибута модуля — если пропатчить только атрибут модуля,
    движок продолжит использовать старую, реальную history_trades_db). Порядок не важен для
    USE_DEMO (читается в момент вызова, не при импорте), но для history_trades_db — важен: обе
    ссылки должны быть переустановлены до того, как движок реально начнёт торговую сессию.
    """
    import database.history_trades_repository as history_trades_repository

    stub = NoOpHistoryTradesDb()
    history_trades_repository.history_trades_db = stub

    import bybit_logic.api_algorithms.short_bu_ts_limit_engine as engine_module

    engine_module.history_trades_db = stub
    engine_module.USE_DEMO = True


@celery_app.task(
    name="demo_showcase_trade",
    bind=True,
    queue="demo_showcase",
    max_retries=2,
    default_retry_delay=5,
)
def demo_showcase_trade(self, symbol: str) -> dict:
    """Демо-сделка для маркетинга — запускается по тому же сигналу, что реальные подписчики."""
    engine_id = os.getenv("CELERY_ENGINE_ID")
    if engine_id:
        symbol = symbol.upper()
        logger.error(
            "demo_showcase_trade выполнен в engine-воркере (CELERY_ENGINE_ID=%s) — отказ, symbol=%s",
            engine_id, symbol,
        )
        return {"status": "error", "symbol": symbol, "error": "wrong_worker"}

    _force_demo_isolation()

    symbol = symbol.upper()

    if not DEMO_SHOWCASE_API_KEY or not DEMO_SHOWCASE_API_SECRET:
        logger.error("demo_showcase_trade: не заданы DEMO_SHOWCASE_API_KEY/SECRET, пропуск")
        return {"status": "error", "symbol": symbol, "error": "missing_credentials"}

    lock_key = f"trade:demo_showcase:{symbol}"
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    lock = redis_client.lock(lock_key, timeout=_LOCK_TTL_SECONDS, blocking=False)
    if not lock.acquire(blocking=False):
        logger.warning("Дубликат demo_showcase_trade отфильтрован: %s", lock_key)
        return {"status": "skipped_duplicate", "symbol": symbol}

    try:
        from bybit_logic.api_algorithms.short_bu_ts_limit_engine import start_trading

        trade_id = start_trading(
            symbol=symbol,
            tg_id=DEMO_SHOWCASE_TG_ID,
            name=DEMO_SHOWCASE_NAME,
            api_key=DEMO_SHOWCASE_API_KEY,
            api_secret=DEMO_SHOWCASE_API_SECRET,
            sum_for_trades=DEMO_SHOWCASE_USDT_AMOUNT,
        )
    except Exception as e:
        logger.error("Ошибка demo_showcase_trade symbol=%s: %s", symbol, e, exc_info=True)
        raise self.retry(exc=e, countdown=5)
    finally:
        try:
            lock.release()
        except Exception:
            pass

    demo_showcase_trades_db.insert_trade(
        {
            "trade_id": trade_id,
            "symbol": symbol,
            "tg_id": DEMO_SHOWCASE_TG_ID,
            "sum_for_trades": DEMO_SHOWCASE_USDT_AMOUNT,
            "created_at": datetime.utcnow(),
        }
    )
    logger.info("demo_showcase_trade запущена: trade_id=%s symbol=%s", trade_id, symbol)
    return {"status": "started", "symbol": symbol, "trade_id": trade_id}
