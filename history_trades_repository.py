from datetime import datetime
from typing import Any

from pymongo import MongoClient
from pymongo import errors as pymongo_errors

from config import MONGO_URI, MONGO_DB
from logger_config import setup_logger

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
            self._users.update_one({"tg_id": int(tg_id)}, {"$inc": inc_fields})
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка apply_user_statistics_delta: %s", e, exc_info=True)
            raise


history_trades_db = HistoryTradesRepository()


def build_trade_doc(
    tg_id: int,
    name: str,
    symbol: str,
    position_info: dict[str, Any],
) -> dict[str, Any]:
    return {
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
        "source": "short_3_limit",
    }
