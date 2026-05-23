from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from pymongo import errors as pymongo_errors

from config import MONGO_URI, MONGO_DB
from logger_config import setup_logger

logger = setup_logger(__name__)


class CustomAlgoRepositoryError(Exception):
    pass


class CustomAlgoValidationError(CustomAlgoRepositoryError):
    pass


def _validate_percentage(value: float | None, field: str) -> float | None:
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError) as exc:
        raise CustomAlgoValidationError(f"{field} должен быть числом") from exc
    if num <= 0 or num > 100:
        raise CustomAlgoValidationError(f"{field} должен быть в диапазоне (0; 100]")
    return num


def normalize_custom_config(raw: dict[str, Any]) -> dict[str, Any]:
    direction = (raw.get("direction") or "long").strip().lower()
    if direction not in {"long", "short"}:
        raise CustomAlgoValidationError("direction должен быть long или short")

    use_trailing_stop = bool(raw.get("use_trailing_stop", False))
    use_stop_loss = bool(raw.get("use_stop_loss", False))
    use_breakeven = bool(raw.get("use_breakeven", False))

    trailing_activate_pct = _validate_percentage(raw.get("trailing_activate_pct"), "trailing_activate_pct")
    trailing_step_pct = _validate_percentage(raw.get("trailing_step_pct"), "trailing_step_pct")
    stop_loss_pct = _validate_percentage(raw.get("stop_loss_pct"), "stop_loss_pct")
    breakeven_pct = _validate_percentage(raw.get("breakeven_pct"), "breakeven_pct")

    order_amount_usdt = raw.get("order_amount_usdt")
    if order_amount_usdt is not None and order_amount_usdt != "":
        try:
            order_amount_usdt = float(order_amount_usdt)
        except (TypeError, ValueError) as exc:
            raise CustomAlgoValidationError("order_amount_usdt должен быть числом") from exc
        if order_amount_usdt <= 0:
            raise CustomAlgoValidationError("order_amount_usdt должен быть больше 0")
    else:
        order_amount_usdt = None

    if not use_trailing_stop:
        trailing_activate_pct = None
        trailing_step_pct = None
    else:
        if trailing_activate_pct is None:
            raise CustomAlgoValidationError("Для trailing_stop нужен trailing_activate_pct")
        if trailing_step_pct is None:
            raise CustomAlgoValidationError("Для trailing_stop нужен trailing_step_pct")

    if not use_stop_loss:
        stop_loss_pct = None
    if not use_breakeven:
        breakeven_pct = None

    return {
        "direction": direction,
        "use_trailing_stop": use_trailing_stop,
        "trailing_activate_pct": trailing_activate_pct,
        "trailing_step_pct": trailing_step_pct,
        "use_stop_loss": use_stop_loss,
        "stop_loss_pct": stop_loss_pct,
        "use_breakeven": use_breakeven,
        "breakeven_pct": breakeven_pct,
        "order_amount_usdt": order_amount_usdt,
    }


class CustomAlgoRepository:
    def __init__(self) -> None:
        self._client: AsyncIOMotorClient = AsyncIOMotorClient(MONGO_URI)
        self._db = self._client[MONGO_DB]
        self._collection: AsyncIOMotorCollection = self._db["custom_algo_configs"]

    async def ensure_indexes(self) -> None:
        await self._collection.create_index("tg_id", unique=True)

    async def get_by_tg_id(self, tg_id: int) -> dict[str, Any] | None:
        try:
            doc = await self._collection.find_one({"tg_id": int(tg_id)}, {"_id": 0})
            return doc
        except pymongo_errors.PyMongoError as exc:
            logger.error("Ошибка get_by_tg_id для %s: %s", tg_id, exc, exc_info=True)
            raise CustomAlgoRepositoryError(str(exc)) from exc

    async def upsert_config(self, tg_id: int, config: dict[str, Any]) -> dict[str, Any]:
        validated = normalize_custom_config(config)
        validated["tg_id"] = int(tg_id)
        validated["updated_at"] = datetime.now(timezone.utc)

        try:
            await self._collection.update_one(
                {"tg_id": int(tg_id)},
                {"$set": validated},
                upsert=True,
            )
            return validated
        except pymongo_errors.PyMongoError as exc:
            logger.error("Ошибка upsert_config для %s: %s", tg_id, exc, exc_info=True)
            raise CustomAlgoRepositoryError(str(exc)) from exc


custom_algo_db = CustomAlgoRepository()
