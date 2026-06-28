"""Sync-чтение users для Celery/engine (без Motor)."""
from __future__ import annotations

from pymongo import MongoClient

from config import MONGO_DB, MONGO_URI


def get_max_concurrent_trades(tg_id: int) -> int:
    client = MongoClient(MONGO_URI)
    try:
        doc = client[MONGO_DB]["users"].find_one(
            {"tg_id": int(tg_id)},
            {"bybit_data.max_concurrent_trades": 1},
        )
        if not doc:
            return 1
        bybit = doc.get("bybit_data") or {}
        try:
            value = int(bybit.get("max_concurrent_trades") or 1)
        except (TypeError, ValueError):
            value = 1
        return max(1, value)
    finally:
        client.close()
