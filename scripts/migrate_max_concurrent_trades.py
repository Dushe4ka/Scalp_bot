"""
Миграция: bybit_data.max_concurrent_trades = 1 для всех пользователей без поля.

Запуск из корня проекта:
    python -m scripts.migrate_max_concurrent_trades
"""
from __future__ import annotations

import asyncio

from database.users_repository import db


async def main() -> None:
    stats_trades = await db.migrate_max_concurrent_trades_default()
    result_lang = await db._collection.update_many(
        {"language_selected": {"$ne": True}},
        {"$set": {"language_selected": True}},
    )
    print(
        f"max_concurrent_trades: matched={stats_trades['matched']} modified={stats_trades['modified']}"
    )
    print(f"language_selected: modified={result_lang.modified_count}")


if __name__ == "__main__":
    asyncio.run(main())
