"""
Настройки приложения в MongoDB (коллекция app_settings).
"""

from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from pymongo import errors as pymongo_errors

from config import MONGO_URI, MONGO_DB
from logger_config import setup_logger

logger = setup_logger(__name__)

UNLIMITED_TRADE_DOC_ID = "trade_amount_unlimited_tg_ids"


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


app_settings_db = AppSettingsRepository()
