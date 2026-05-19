"""Execute one trade on a dedicated engine Celery worker (Phase 2)."""
from __future__ import annotations

import os

from celery_app.celery_config import celery_app
from celery_app.trade_orchestrator import release_engine_slot
from celery_app.utils import setup_project_path
from logger_config import setup_logger

logger = setup_logger(__name__)


@celery_app.task(
    name="engine_execute_trade",
    bind=True,
    max_retries=2,
    default_retry_delay=3,
)
def engine_execute_trade(
    self,
    trade_id: str,
    symbol: str,
    tg_id: int,
    name: str,
    api_key: str,
    api_secret: str,
    sum_for_trades: float,
    engine_id: str | None = None,
):
    setup_project_path()
    eid = engine_id or os.getenv("CELERY_ENGINE_ID", "?")
    logger.info(
        "engine_execute_trade: engine=%s trade_id=%s symbol=%s tg_id=%s",
        eid,
        trade_id,
        symbol,
        tg_id,
    )
    try:
        from bybit_logic.api_algorithms.short_bu_ts_limit_engine import get_async_trade_engine

        engine = get_async_trade_engine()
        engine.submit_trade(
            symbol=symbol,
            tg_id=tg_id,
            name=name,
            api_key=api_key,
            api_secret=api_secret,
            sum_for_trades=float(sum_for_trades),
            trade_id=trade_id,
        )
        return {
            "status": "submitted",
            "trade_id": trade_id,
            "engine_id": str(eid),
            "running_count": engine.running_count(),
        }
    except Exception as exc:
        release_engine_slot(eid)
        logger.error("engine_execute_trade failed: %s", exc, exc_info=True)
        raise
