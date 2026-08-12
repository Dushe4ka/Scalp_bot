"""Аудит-лог demo-сделок для маркетинга + no-op заглушка history_trades_db для изоляции."""
from __future__ import annotations

from typing import Any

from pymongo import MongoClient
from pymongo import errors as pymongo_errors

from config import MONGO_URI, MONGO_DB
from logger_config import setup_logger

logger = setup_logger(__name__)


class DemoShowcaseTradesRepository:
    """Чисто аудит-лог (НЕ history_trades) — не участвует в UI бота, не влияет на статистику."""

    def __init__(self) -> None:
        self._client = MongoClient(MONGO_URI)
        self._db = self._client[MONGO_DB]
        self._collection = self._db["demo_showcase_trades"]

    def insert_trade(self, doc: dict[str, Any]) -> None:
        try:
            self._collection.insert_one(doc)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка insert_trade (demo_showcase_trades): %s", e, exc_info=True)
            raise


demo_showcase_trades_db = DemoShowcaseTradesRepository()


class NoOpHistoryTradesDb:
    """
    Заглушка вместо database.history_trades_repository.history_trades_db для процесса
    demo_showcase: сделки не должны попадать в реальную историю/статистику пользователя.
    Сигнатуры зеркалят только те методы HistoryTradesRepository, которые реально вызывает
    bybit_logic.api_algorithms.short_bu_ts_limit_engine.TradeSession.
    """

    def save_trade_by_state(self, trade_doc: dict[str, Any], state: str) -> None:
        logger.debug("NoOpHistoryTradesDb.save_trade_by_state подавлен (demo_showcase): state=%s", state)

    def apply_user_statistics_delta(self, tg_id: int, pnl_usdt: float) -> None:
        logger.debug(
            "NoOpHistoryTradesDb.apply_user_statistics_delta подавлен (demo_showcase): tg_id=%s",
            tg_id,
        )

    def count_active_trades(self, tg_id: int) -> int:
        return 0
