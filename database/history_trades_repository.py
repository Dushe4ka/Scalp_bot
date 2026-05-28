from datetime import datetime
from typing import Any

from pymongo import MongoClient
from pymongo import errors as pymongo_errors

from config import MONGO_URI, MONGO_DB
from logger_config import setup_logger
from database.user_statistics_coercion import coerce_user_statistics_sync

logger = setup_logger(__name__)


class HistoryTradesRepository:
    def __init__(self) -> None:
        self._client = MongoClient(MONGO_URI)
        self._db = self._client[MONGO_DB]
        self._history = self._db["history_trades"]
        self._users = self._db["users"]

    def insert_closed_trade(self, trade_doc: dict[str, Any]) -> None:
        try:
            self._history.insert_one(trade_doc)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка insert_closed_trade: %s", e, exc_info=True)
            raise

    def save_trade_by_state(self, trade_doc: dict[str, Any], state: str) -> None:
        """
        Сохраняет историю сделки по состоянию:
        - active: создаёт/обновляет активную запись (upsert по trade_id + tg_id)
        - closed: переводит существующую запись в closed и обновляет поля
        """
        normalized_state = str(state).strip().lower()
        if normalized_state not in ("active", "closed"):
            raise ValueError(f"Некорректный state={state}. Ожидается active|closed")

        payload = dict(trade_doc)
        payload["state"] = normalized_state
        payload["updated_at"] = datetime.utcnow()
        if normalized_state == "active":
            payload.setdefault("created_at", datetime.utcnow())
        else:
            payload["closed_at"] = datetime.utcnow()

        trade_id = payload.get("trade_id")
        tg_id = payload.get("tg_id")
        symbol = payload.get("symbol")
        if not trade_id or tg_id is None:
            raise ValueError("Для save_trade_by_state обязательны trade_id и tg_id")

        try:
            query = {"trade_id": trade_id, "tg_id": int(tg_id)}
            if normalized_state == "active":
                self._history.update_one(query, {"$set": payload}, upsert=True)
                return

            result = self._history.update_one(query, {"$set": payload}, upsert=False)
            # Fallback для старых записей без trade_id.
            if result.matched_count == 0 and symbol:
                self._history.update_one(
                    {"tg_id": int(tg_id), "symbol": symbol, "state": "active"},
                    {"$set": payload},
                    upsert=False,
                )
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка save_trade_by_state: %s", e, exc_info=True)
            raise

    def apply_user_statistics_delta(self, tg_id: int, pnl_usdt: float) -> None:
        inc_fields: dict[str, float | int] = {
            "statistics.total_trades": 1,
            "statistics.total_pnl": float(pnl_usdt),
        }
        if pnl_usdt > 0:
            inc_fields["statistics.positive_trades"] = 1
            inc_fields["statistics.sum_positive_trades"] = float(pnl_usdt)
        elif pnl_usdt < 0:
            inc_fields["statistics.negative_trades"] = 1
            inc_fields["statistics.sum_negative_trades"] = abs(float(pnl_usdt))

        try:
            coerce_user_statistics_sync(self._users, int(tg_id))
            self._users.update_one({"tg_id": int(tg_id)}, {"$inc": inc_fields})
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка apply_user_statistics_delta: %s", e, exc_info=True)
            raise

    def list_user_trades(self, tg_id: int, limit: int = 10) -> list[dict[str, Any]]:
        """Последние сделки пользователя по убыванию created_at."""
        lim = max(1, min(int(limit), 50))
        try:
            cursor = (
                self._history.find({"tg_id": int(tg_id)}, {"_id": 0})
                .sort("created_at", -1)
                .limit(lim)
            )
            return list(cursor)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка list_user_trades: %s", e, exc_info=True)
            raise

    def count_user_trades(self, tg_id: int) -> int:
        try:
            return int(self._history.count_documents({"tg_id": int(tg_id)}))
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка count_user_trades: %s", e, exc_info=True)
            raise

    def list_user_trades_page(self, tg_id: int, *, page: int, page_size: int) -> list[dict[str, Any]]:
        pg = max(0, int(page))
        size = max(1, min(int(page_size), 50))
        skip = pg * size
        try:
            cursor = (
                self._history.find({"tg_id": int(tg_id)}, {"_id": 0})
                .sort("created_at", -1)
                .skip(skip)
                .limit(size)
            )
            return list(cursor)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка list_user_trades_page: %s", e, exc_info=True)
            raise


history_trades_db = HistoryTradesRepository()


def build_trade_doc(
    tg_id: int,
    name: str,
    symbol: str,
    position_info: dict[str, Any],
    *,
    trade_id: str | None = None,
    state: str = "closed",
) -> dict[str, Any]:
    return {
        "trade_id": trade_id,
        "tg_id": int(tg_id),
        "name": name,
        "symbol": symbol,
        "side": position_info.get("side", ""),
        "entry_price": float(position_info.get("entry_price") or 0),
        "exit_price": float(position_info.get("exit_price") or 0),
        "size": float(position_info.get("size") or 0),
        "pnl_usdt": float(position_info.get("pnl_usdt") or 0),
        "open_time": position_info.get("open_time"),
        "close_time": position_info.get("close_time"),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "state": state,
        "source": "short_3_limit",
    }
