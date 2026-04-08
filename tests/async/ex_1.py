"""
Тестовый запуск реальной demo-торговли через AsyncTradeEngine (1 пользователь).

Что нужно перед запуском:
1) Поднять инфраструктуру проекта (Redis/Celery worker, если уведомления включены).
2) Заполнить .env:
   - DEMO_API_KEY
   - DEMO_API_SECRET
   - TRADE_SYMBOL (например, BTCUSDT)
   - TRADE_SUM_USDT (например, 10)
   - TG_ID (например, 123456789)
   - TG_NAME (например, "Test User")

Запуск:
    python tests/async/ex_1.py
"""

from __future__ import annotations

import os
import time

import dotenv

from bybit_logic._update.async_src import short_bu_ts_limit_multiuser as engine_module
from bybit_logic._update.async_src.short_bu_ts_limit_multiuser import get_async_trade_engine

dotenv.load_dotenv()


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Переменная окружения {name} не задана")
    return value


def main() -> None:
    # В исходном модуле по умолчанию стоит USE_DEMO=False.
    # Для теста реальной торговли на demo-ключах принудительно включаем demo-режим.
    engine_module.USE_DEMO = True

    symbol = _require_env("TRADE_SYMBOL").upper()
    demo_api_key = _require_env("DEMO_API_KEY")
    demo_api_secret = _require_env("DEMO_API_SECRET")
    tg_id = int(os.getenv("TG_ID", "1"))
    name = os.getenv("TG_NAME", "Demo User")
    sum_for_trades = float(os.getenv("TRADE_SUM_USDT", "10"))

    print("=== START DEMO TRADE TEST ===")
    print(f"symbol={symbol}, tg_id={tg_id}, name={name}, sum={sum_for_trades} USDT")
    print("Нажми Ctrl+C для ручной остановки наблюдения.")

    engine = get_async_trade_engine()
    trade_id = engine.submit_trade(
        symbol=symbol,
        tg_id=tg_id,
        name=name,
        api_key=demo_api_key,
        api_secret=demo_api_secret,
        sum_for_trades=sum_for_trades,
    )
    print(f"trade_id={trade_id}")

    try:
        while True:
            print(f"[heartbeat] running_sessions={engine.running_count()}")
            time.sleep(5)
            if engine.running_count() == 0:
                print("Сессия завершена.")
                break
    except KeyboardInterrupt:
        print("\nОстановлено пользователем. Активные сессии продолжат жить в фоне engine thread.")


if __name__ == "__main__":
    main()