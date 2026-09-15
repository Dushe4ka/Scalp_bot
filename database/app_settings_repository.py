"""
Настройки приложения в MongoDB (коллекция app_settings).
"""

from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from pymongo import errors as pymongo_errors

from config import MONGO_URI, MONGO_DB, SUBSCRIPTION_PRICE_USD
from logger_config import setup_logger

logger = setup_logger(__name__)

UNLIMITED_TRADE_DOC_ID = "trade_amount_unlimited_tg_ids"
SUBSCRIPTION_PRICE_DOC_ID = "subscription_price"
DEFAULT_SUBSCRIPTION_OLD_PRICE_USD = SUBSCRIPTION_PRICE_USD
DEFAULT_SUBSCRIPTION_PRICE_USD = 59.0


class AppSettingsRepositoryError(Exception):
    """Базовое исключение репозитория app_settings."""


class AppSettingsRepository:
    def __init__(self) -> None:
        self._client: AsyncIOMotorClient = AsyncIOMotorClient(MONGO_URI)
        self._db = self._client[MONGO_DB]
        self._collection: AsyncIOMotorCollection = self._db["app_settings"]

    async def ensure_unlimited_trade_amount_admins(self, admin_ids: list[int]) -> dict[str, int]:
        """Добавляет админов из env в список без лимита (без дубликатов)."""
        normalized = sorted({int(tg_id) for tg_id in admin_ids if tg_id})
        if not normalized:
            return {"added": 0, "total": 0}

        logger.info("Синхронизация trade_amount_unlimited с ADMIN_IDS: %s", normalized)
        try:
            doc_before = await self._collection.find_one({"_id": UNLIMITED_TRADE_DOC_ID})
            before_set = {int(x) for x in (doc_before or {}).get("tg_ids", [])}
            await self._collection.update_one(
                {"_id": UNLIMITED_TRADE_DOC_ID},
                {"$addToSet": {"tg_ids": {"$each": normalized}}},
                upsert=True,
            )
            doc_after = await self._collection.find_one({"_id": UNLIMITED_TRADE_DOC_ID})
            after_set = {int(x) for x in (doc_after or {}).get("tg_ids", [])}
            return {
                "added": len(after_set - before_set),
                "total": len(after_set),
            }
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка ensure_unlimited_trade_amount_admins: %s", e, exc_info=True)
            raise AppSettingsRepositoryError(str(e)) from e

    async def is_unlimited_trade_amount(self, tg_id: int) -> bool:
        try:
            doc = await self._collection.find_one({"_id": UNLIMITED_TRADE_DOC_ID})
            if not doc:
                return False
            return int(tg_id) in {int(x) for x in doc.get("tg_ids", [])}
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка is_unlimited_trade_amount tg_id=%s: %s", tg_id, e, exc_info=True)
            raise AppSettingsRepositoryError(str(e)) from e

    async def add_unlimited_trade_amount(self, tg_id: int) -> bool:
        try:
            result = await self._collection.update_one(
                {"_id": UNLIMITED_TRADE_DOC_ID},
                {"$addToSet": {"tg_ids": int(tg_id)}},
                upsert=True,
            )
            return bool(result.modified_count or result.upserted_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка add_unlimited_trade_amount tg_id=%s: %s", tg_id, e, exc_info=True)
            raise AppSettingsRepositoryError(str(e)) from e

    async def remove_unlimited_trade_amount(self, tg_id: int) -> bool:
        try:
            result = await self._collection.update_one(
                {"_id": UNLIMITED_TRADE_DOC_ID},
                {"$pull": {"tg_ids": int(tg_id)}},
            )
            return result.modified_count > 0
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка remove_unlimited_trade_amount tg_id=%s: %s", tg_id, e, exc_info=True)
            raise AppSettingsRepositoryError(str(e)) from e

    async def get_unlimited_trade_amount_doc(self) -> dict[str, Any] | None:
        try:
            return await self._collection.find_one({"_id": UNLIMITED_TRADE_DOC_ID})
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка get_unlimited_trade_amount_doc: %s", e, exc_info=True)
            raise AppSettingsRepositoryError(str(e)) from e

    async def get_subscription_price(self) -> dict[str, float]:
        """Актуальная цена подписки + старая (зачёркиваемая) цена для скидочного блока."""
        try:
            doc = await self._collection.find_one({"_id": SUBSCRIPTION_PRICE_DOC_ID})
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка get_subscription_price: %s", e, exc_info=True)
            raise AppSettingsRepositoryError(str(e)) from e

        if not doc:
            return {
                "price_usd": DEFAULT_SUBSCRIPTION_PRICE_USD,
                "old_price_usd": DEFAULT_SUBSCRIPTION_OLD_PRICE_USD,
            }
        return {
            "price_usd": float(doc.get("price_usd", DEFAULT_SUBSCRIPTION_PRICE_USD)),
            "old_price_usd": float(doc.get("old_price_usd", DEFAULT_SUBSCRIPTION_OLD_PRICE_USD)),
        }

    async def set_subscription_price(
        self, price_usd: float, old_price_usd: float | None = None
    ) -> dict[str, float]:
        """Обновляет цену подписки. old_price_usd не передан — старая цена не меняется."""
        update: dict[str, float] = {"price_usd": float(price_usd)}
        if old_price_usd is not None:
            update["old_price_usd"] = float(old_price_usd)

        try:
            await self._collection.update_one(
                {"_id": SUBSCRIPTION_PRICE_DOC_ID},
                {"$set": update},
                upsert=True,
            )
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка set_subscription_price: %s", e, exc_info=True)
            raise AppSettingsRepositoryError(str(e)) from e

        return await self.get_subscription_price()


app_settings_db = AppSettingsRepository()
