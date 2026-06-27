"""Sync-доступ к users для Celery: уведомления об истечении API-ключа."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pymongo import MongoClient
from pymongo import errors as pymongo_errors

from config import MONGO_DB, MONGO_URI
from logger_config import setup_logger

logger = setup_logger(__name__)

_NOTIFY_API_3D = "notify_api_key_3d"
_NOTIFY_API_1D = "notify_api_key_1d"
_NOTIFY_API_EXPIRED = "notify_api_key_expired"


class ApiKeyLifecycleRepository:
    def __init__(self) -> None:
        self._client = MongoClient(MONGO_URI)
        self._collection = self._client[MONGO_DB]["users"]

    def list_users_with_api_key_expiry(self) -> list[dict[str, Any]]:
        try:
            cursor = self._collection.find(
                {
                    "bybit_data.api_key": {"$nin": ["", None]},
                    "bybit_data.api_secret": {"$nin": ["", None]},
                    "bybit_data.api_key_expired_at": {"$ne": None},
                },
                {
                    "_id": 0,
                    "tg_id": 1,
                    "name": 1,
                    "language": 1,
                    "bybit_data": 1,
                },
            )
            return list(cursor)
        except pymongo_errors.PyMongoError as e:
            logger.error("list_users_with_api_key_expiry failed: %s", e, exc_info=True)
            raise

    def mark_notification_sent(self, tg_id: int, field: str, expired_at: datetime) -> None:
        if field not in (_NOTIFY_API_3D, _NOTIFY_API_1D, _NOTIFY_API_EXPIRED):
            raise ValueError(f"Unknown notification field: {field}")
        try:
            self._collection.update_one(
                {"tg_id": int(tg_id)},
                {"$set": {f"bybit_data.{field}": expired_at}},
            )
        except pymongo_errors.PyMongoError as e:
            logger.error(
                "mark_api_key_notification_sent tg_id=%s field=%s: %s",
                tg_id,
                field,
                e,
                exc_info=True,
            )
            raise


api_key_lifecycle_db = ApiKeyLifecycleRepository()
