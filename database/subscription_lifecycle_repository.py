"""Sync-доступ к users для Celery: проверка срока подписки и отметки уведомлений."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pymongo import MongoClient
from pymongo import errors as pymongo_errors

from config import MONGO_DB, MONGO_URI
from logger_config import setup_logger

logger = setup_logger(__name__)

_NOTIFY_3D = "notify_3d_for_end"
_NOTIFY_1D = "notify_1d_for_end"
_NOTIFY_EXPIRED = "notify_expired_for_end"


class SubscriptionLifecycleRepository:
    def __init__(self) -> None:
        self._client = MongoClient(MONGO_URI)
        self._collection = self._client[MONGO_DB]["users"]

    def list_active_subscriptions(self) -> list[dict[str, Any]]:
        """Активные подписки с датой окончания."""
        try:
            cursor = self._collection.find(
                {
                    "subscription_data.subscription": True,
                    "subscription_data.end_subscription_date": {"$ne": None},
                },
                {
                    "_id": 0,
                    "tg_id": 1,
                    "name": 1,
                    "language": 1,
                    "subscription_data": 1,
                },
            )
            return list(cursor)
        except pymongo_errors.PyMongoError as e:
            logger.error("list_active_subscriptions failed: %s", e, exc_info=True)
            raise

    def deactivate_subscription(self, tg_id: int) -> None:
        try:
            self._collection.update_one(
                {"tg_id": int(tg_id)},
                {
                    "$set": {
                        "subscription_data.subscription": False,
                        "subscription_data.wait_sub_confirmation": False,
                    }
                },
            )
        except pymongo_errors.PyMongoError as e:
            logger.error("deactivate_subscription tg_id=%s: %s", tg_id, e, exc_info=True)
            raise

    def mark_notification_sent(self, tg_id: int, field: str, end_date: datetime) -> None:
        if field not in (_NOTIFY_3D, _NOTIFY_1D, _NOTIFY_EXPIRED):
            raise ValueError(f"Unknown notification field: {field}")
        try:
            self._collection.update_one(
                {"tg_id": int(tg_id)},
                {"$set": {f"subscription_data.{field}": end_date}},
            )
        except pymongo_errors.PyMongoError as e:
            logger.error(
                "mark_notification_sent tg_id=%s field=%s: %s",
                tg_id,
                field,
                e,
                exc_info=True,
            )
            raise


subscription_lifecycle_db = SubscriptionLifecycleRepository()
