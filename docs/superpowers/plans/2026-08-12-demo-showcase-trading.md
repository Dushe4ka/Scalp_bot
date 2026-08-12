# Demo-показ сделок для маркетинга — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Дать пользователю `tg_id=490882969` реальный, автоматический demo-Bybit трейдинг по тем же
сигналам, что и у настоящих подписчиков (`/short_3_limit`), с крупной фиксированной суммой сделки —
для маркетинговых скриншотов, без риска для боевых денег и без изменения боевого торгового движка.

**Architecture:** Отдельный Celery-воркер на своей очереди `demo_showcase`, с собственным экземпляром
`AsyncTradeEngine`. Переиспользует классы `TradeSession`/`AsyncTradeEngine`/`start_trading()` из
`bybit_logic/api_algorithms/short_bu_ts_limit_engine.py` **без единой правки в этом файле** —
изоляция достигается на уровне ОС-процесса: этот процесс форсирует `USE_DEMO=True` и подменяет
`history_trades_db` на no-op заглушку сразу после старта, до первого импорта движка.

**Tech Stack:** Python 3.12, Celery, Redis (idempotency lock + broker), pymongo (sync, аудит-коллекция),
`unittest` (stdlib, без pytest — тесты гоняются через `python -m unittest`).

## Global Constraints

- Zero правок в `bybit_logic/api_algorithms/short_bu_ts_limit_engine.py` — вся новая логика только
  в `demo_showcase/`.
- Хук в `server_api/routes/trading.py` — только один импорт + один вызов, без изменения существующей
  логики fan-out реальным подписчикам.
- Demo-сделки не должны появляться в `history_trades` / `users.statistics` (реальный профиль/история
  админа `tg_id=490882969` не должны исказиться).
- Тесты — только `unittest` (`python -m unittest tests.test_demo_showcase -v`), без pytest,
  без реального Redis/Mongo/Bybit — всё, что требует реальной инфраструктуры, помечено как
  Manual/integration (последняя задача плана).

---

### Task 1: Пакет `demo_showcase` и env-конфигурация

**Files:**
- Create: `demo_showcase/__init__.py`
- Create: `demo_showcase/config.py`

**Interfaces:**
- Produces: `demo_showcase.config.DEMO_SHOWCASE_ENABLED: bool`,
  `demo_showcase.config.DEMO_SHOWCASE_TG_ID: int`, `demo_showcase.config.DEMO_SHOWCASE_NAME: str`,
  `demo_showcase.config.DEMO_SHOWCASE_API_KEY: str`, `demo_showcase.config.DEMO_SHOWCASE_API_SECRET: str`,
  `demo_showcase.config.DEMO_SHOWCASE_USDT_AMOUNT: float`

Без unit-теста: в этом кодбейзе ни один env-конфиг модуль (`config.py`, `celery_app/config.py`,
`bybit_logic/feeds/feed_config.py`) не покрыт unit-тестами — это read-only обёртка над `os.getenv`,
проверяется импортом. Task right-sizing здесь — implement + smoke-check, без искусственного теста.

- [ ] **Step 1: Создать пакет и конфиг**

`demo_showcase/__init__.py`:

```python
"""Demo-показ сделок для маркетинга (изолированный demo-Bybit трейдинг, tg_id 490882969)."""
```

`demo_showcase/config.py`:

```python
"""Env-конфигурация demo-показа сделок для маркетинга (изолированный Celery-воркер)."""
from __future__ import annotations

import os

import dotenv

dotenv.load_dotenv()


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("true", "1", "yes")


DEMO_SHOWCASE_ENABLED = _bool("DEMO_SHOWCASE_ENABLED", False)
DEMO_SHOWCASE_TG_ID = int(os.getenv("DEMO_SHOWCASE_TG_ID", "490882969"))
DEMO_SHOWCASE_NAME = os.getenv("DEMO_SHOWCASE_NAME", "demo_showcase")
DEMO_SHOWCASE_API_KEY = (os.getenv("DEMO_SHOWCASE_API_KEY") or "").strip()
DEMO_SHOWCASE_API_SECRET = (os.getenv("DEMO_SHOWCASE_API_SECRET") or "").strip()
DEMO_SHOWCASE_USDT_AMOUNT = float(os.getenv("DEMO_SHOWCASE_USDT_AMOUNT", "5000"))
```

- [ ] **Step 2: Smoke-check импорта**

Run: `python -c "from demo_showcase import config; print(config.DEMO_SHOWCASE_ENABLED, config.DEMO_SHOWCASE_TG_ID, config.DEMO_SHOWCASE_USDT_AMOUNT)"`
Expected: `False 490882969 5000.0` (пока `.env` не содержит `DEMO_SHOWCASE_*` — значения по умолчанию).

- [ ] **Step 3: Commit**

```bash
git add demo_showcase/__init__.py demo_showcase/config.py
git commit -m "feat: demo_showcase package skeleton + env config"
```

---

### Task 2: Аудит-репозиторий + no-op заглушка `history_trades_db`

**Files:**
- Create: `demo_showcase/repository.py`
- Create: `tests/test_demo_showcase.py`

**Interfaces:**
- Consumes: `config.MONGO_URI: str`, `config.MONGO_DB: str` (уже существуют в `config.py`)
- Produces: `demo_showcase.repository.DemoShowcaseTradesRepository.insert_trade(doc: dict) -> None`,
  `demo_showcase.repository.demo_showcase_trades_db: DemoShowcaseTradesRepository` (модульный синглтон),
  `demo_showcase.repository.NoOpHistoryTradesDb` с методами
  `save_trade_by_state(trade_doc: dict, state: str) -> None`,
  `apply_user_statistics_delta(tg_id: int, pnl_usdt: float) -> None`,
  `count_active_trades(tg_id: int) -> int` (всегда возвращает `0`)

**Почему нужна заглушка:** `TradeSession` (переиспользуемая без изменений) сама пишет в
`history_trades`/`users.statistics` через модульный синглтон `history_trades_db`, импортированный в
`short_bu_ts_limit_engine.py` (и ещё раз локально внутри `_submit_trade_async` — то есть подменять
нужно **атрибут модуля `database.history_trades_repository`**, а не имя внутри
`short_bu_ts_limit_engine`, чтобы сработали оба места импорта). Это делается в Task 3.

- [ ] **Step 1: Написать падающий тест для `NoOpHistoryTradesDb`**

Создать `tests/test_demo_showcase.py`:

```python
"""Unit tests for demo_showcase (mocked — no real Bybit/Celery/Redis/Mongo)."""
from __future__ import annotations

import unittest

from demo_showcase.repository import NoOpHistoryTradesDb


class NoOpHistoryTradesDbTests(unittest.TestCase):
    def test_methods_are_safe_no_ops(self):
        stub = NoOpHistoryTradesDb()
        stub.save_trade_by_state({"trade_id": "x"}, "active")
        stub.apply_user_statistics_delta(1, 10.0)
        self.assertEqual(stub.count_active_trades(1), 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Запустить тест и убедиться, что он падает**

Run: `python -m unittest tests.test_demo_showcase -v`
Expected: `FAIL` / `ERROR` — `ModuleNotFoundError: No module named 'demo_showcase.repository'` (файл ещё не создан).

- [ ] **Step 3: Реализовать `demo_showcase/repository.py`**

```python
"""Аудит-лог demo-сделок для маркетинга + no-op заглушка history_trades_db для изоляции."""
from __future__ import annotations

from typing import Any

from pymongo import MongoClient
from pymongo import errors as pymongo_errors

from config import MONGO_URI, MONGO_DB
from logger_config import setup_logger

logger = setup_logger(__name__)


class DemoShowcaseTradesRepository:
    """Чисто аудит-лог (НЕ history_trades) — не участвует в UI бота, не влияет на статистику."""

    def __init__(self) -> None:
        self._client = MongoClient(MONGO_URI)
        self._db = self._client[MONGO_DB]
        self._collection = self._db["demo_showcase_trades"]

    def insert_trade(self, doc: dict[str, Any]) -> None:
        try:
            self._collection.insert_one(doc)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка insert_trade (demo_showcase_trades): %s", e, exc_info=True)
            raise


demo_showcase_trades_db = DemoShowcaseTradesRepository()


class NoOpHistoryTradesDb:
    """
    Заглушка вместо database.history_trades_repository.history_trades_db для процесса
    demo_showcase: сделки не должны попадать в реальную историю/статистику пользователя.
    Сигнатуры зеркалят только те методы HistoryTradesRepository, которые реально вызывает
    bybit_logic.api_algorithms.short_bu_ts_limit_engine.TradeSession.
    """

    def save_trade_by_state(self, trade_doc: dict[str, Any], state: str) -> None:
        logger.debug("NoOpHistoryTradesDb.save_trade_by_state подавлен (demo_showcase): state=%s", state)

    def apply_user_statistics_delta(self, tg_id: int, pnl_usdt: float) -> None:
        logger.debug(
            "NoOpHistoryTradesDb.apply_user_statistics_delta подавлен (demo_showcase): tg_id=%s",
            tg_id,
        )

    def count_active_trades(self, tg_id: int) -> int:
        return 0
```

- [ ] **Step 4: Запустить тест и убедиться, что он проходит**

Run: `python -m unittest tests.test_demo_showcase -v`
Expected: `test_methods_are_safe_no_ops ... ok`

- [ ] **Step 5: Commit**

```bash
git add demo_showcase/repository.py tests/test_demo_showcase.py
git commit -m "feat: demo_showcase audit repo + no-op history_trades stub"
```

---

### Task 3: Celery-задача `demo_showcase_trade` + принудительная изоляция

**Files:**
- Create: `demo_showcase/tasks.py`
- Modify: `tests/test_demo_showcase.py`

**Interfaces:**
- Consumes: `demo_showcase.config.{DEMO_SHOWCASE_API_KEY,DEMO_SHOWCASE_API_SECRET,DEMO_SHOWCASE_NAME,
  DEMO_SHOWCASE_TG_ID,DEMO_SHOWCASE_USDT_AMOUNT}` (Task 1),
  `demo_showcase.repository.{NoOpHistoryTradesDb,demo_showcase_trades_db}` (Task 2),
  `celery_app.celery_config.celery_app`, `celery_app.config.REDIS_URL`,
  `bybit_logic.api_algorithms.short_bu_ts_limit_engine.start_trading(symbol: str, tg_id: int,
  name: str, api_key: str, api_secret: str, sum_for_trades: float) -> str` (существующая функция,
  **не менять**), `database.history_trades_repository` (модуль — подменяем его атрибут
  `history_trades_db`)
- Produces: `demo_showcase.tasks._force_demo_isolation() -> None`,
  Celery-задача с именем `"demo_showcase_trade"` на очереди `"demo_showcase"`

**Важно про изоляцию:** `_force_demo_isolation()` обязана выполниться **до первого импорта**
`bybit_logic.api_algorithms.short_bu_ts_limit_engine` в этом процессе — иначе
`short_bu_ts_limit_engine.USE_DEMO` (прочитан при импорте модуля) останется `False`. Поэтому в самой
задаче `start_trading` импортируется **после** вызова `_force_demo_isolation()`, лениво, внутри тела
задачи, а не в верхней части файла.

- [ ] **Step 1: Написать падающий тест для `_force_demo_isolation`**

Добавить в `tests/test_demo_showcase.py` (после существующего класса `NoOpHistoryTradesDbTests`,
перед `if __name__ == "__main__":`):

```python
from unittest.mock import MagicMock, patch


class DemoShowcaseIsolationTests(unittest.TestCase):
    def test_force_demo_isolation_sets_use_demo_true_and_stubs_history(self):
        import bybit_logic.api_algorithms.short_bu_ts_limit_engine as engine_module
        import database.history_trades_repository as history_trades_repository
        from demo_showcase.repository import NoOpHistoryTradesDb
        from demo_showcase.tasks import _force_demo_isolation

        original_use_demo = engine_module.USE_DEMO
        original_history_db = history_trades_repository.history_trades_db
        try:
            _force_demo_isolation()
            self.assertTrue(engine_module.USE_DEMO)
            self.assertIsInstance(history_trades_repository.history_trades_db, NoOpHistoryTradesDb)
        finally:
            engine_module.USE_DEMO = original_use_demo
            history_trades_repository.history_trades_db = original_history_db


class DemoShowcaseTaskTests(unittest.TestCase):
    def test_skips_when_credentials_missing(self):
        with patch("demo_showcase.tasks.DEMO_SHOWCASE_API_KEY", ""), \
             patch("demo_showcase.tasks.DEMO_SHOWCASE_API_SECRET", ""), \
             patch("demo_showcase.tasks._force_demo_isolation") as mock_isolation:
            from demo_showcase.tasks import demo_showcase_trade

            result = demo_showcase_trade.run(symbol="btcusdt")

        mock_isolation.assert_called_once()
        self.assertEqual(result, {"status": "error", "symbol": "BTCUSDT", "error": "missing_credentials"})

    def test_starts_trade_with_demo_credentials_and_audits(self):
        fake_redis_client = MagicMock()
        fake_lock = MagicMock()
        fake_lock.acquire.return_value = True
        fake_redis_client.lock.return_value = fake_lock

        with patch("demo_showcase.tasks.DEMO_SHOWCASE_API_KEY", "demo_key"), \
             patch("demo_showcase.tasks.DEMO_SHOWCASE_API_SECRET", "demo_secret"), \
             patch("demo_showcase.tasks.DEMO_SHOWCASE_TG_ID", 490882969), \
             patch("demo_showcase.tasks.DEMO_SHOWCASE_NAME", "demo_showcase"), \
             patch("demo_showcase.tasks.DEMO_SHOWCASE_USDT_AMOUNT", 5000.0), \
             patch("demo_showcase.tasks._force_demo_isolation") as mock_isolation, \
             patch("demo_showcase.tasks.redis.Redis.from_url", return_value=fake_redis_client), \
             patch("demo_showcase.tasks.demo_showcase_trades_db") as mock_audit_db, \
             patch(
                 "bybit_logic.api_algorithms.short_bu_ts_limit_engine.start_trading",
                 return_value="490882969:BTCUSDT:abc123",
             ) as mock_start_trading:
            from demo_showcase.tasks import demo_showcase_trade

            result = demo_showcase_trade.run(symbol="btcusdt")

        mock_isolation.assert_called_once()
        mock_start_trading.assert_called_once_with(
            symbol="BTCUSDT",
            tg_id=490882969,
            name="demo_showcase",
            api_key="demo_key",
            api_secret="demo_secret",
            sum_for_trades=5000.0,
        )
        mock_audit_db.insert_trade.assert_called_once()
        fake_lock.release.assert_called_once()
        self.assertEqual(result["status"], "started")
        self.assertEqual(result["trade_id"], "490882969:BTCUSDT:abc123")

    def test_skips_duplicate_when_lock_not_acquired(self):
        fake_redis_client = MagicMock()
        fake_lock = MagicMock()
        fake_lock.acquire.return_value = False
        fake_redis_client.lock.return_value = fake_lock

        with patch("demo_showcase.tasks.DEMO_SHOWCASE_API_KEY", "demo_key"), \
             patch("demo_showcase.tasks.DEMO_SHOWCASE_API_SECRET", "demo_secret"), \
             patch("demo_showcase.tasks._force_demo_isolation"), \
             patch("demo_showcase.tasks.redis.Redis.from_url", return_value=fake_redis_client), \
             patch(
                 "bybit_logic.api_algorithms.short_bu_ts_limit_engine.start_trading"
             ) as mock_start_trading:
            from demo_showcase.tasks import demo_showcase_trade

            result = demo_showcase_trade.run(symbol="btcusdt")

        mock_start_trading.assert_not_called()
        self.assertEqual(result, {"status": "skipped_duplicate", "symbol": "BTCUSDT"})
```

- [ ] **Step 2: Запустить тесты и убедиться, что они падают**

Run: `python -m unittest tests.test_demo_showcase -v`
Expected: `FAIL` / `ERROR` — `ModuleNotFoundError: No module named 'demo_showcase.tasks'`.

- [ ] **Step 3: Реализовать `demo_showcase/tasks.py`**

```python
"""Celery-задача demo-показа сделок для маркетинга.

Работает ТОЛЬКО в собственном изолированном воркер-процессе (очередь demo_showcase,
--concurrency=1). Форсирует demo-режим и подавляет запись в history_trades/statistics
для этого процесса — см. docs/superpowers/specs/2026-08-11-demo-showcase-trading-design.md.
"""
from __future__ import annotations

from datetime import datetime

import redis

from celery_app.celery_config import celery_app
from celery_app.config import REDIS_URL
from demo_showcase.config import (
    DEMO_SHOWCASE_API_KEY,
    DEMO_SHOWCASE_API_SECRET,
    DEMO_SHOWCASE_NAME,
    DEMO_SHOWCASE_TG_ID,
    DEMO_SHOWCASE_USDT_AMOUNT,
)
from demo_showcase.repository import NoOpHistoryTradesDb, demo_showcase_trades_db
from logger_config import setup_logger

logger = setup_logger(__name__)

_LOCK_TTL_SECONDS = 60 * 60 * 4


def _force_demo_isolation() -> None:
    """
    Форсирует demo-режим и подавляет запись в history_trades для ЭТОГО процесса.
    Обязана вызываться до первого импорта short_bu_ts_limit_engine в этом процессе —
    иначе module-level USE_DEMO (читается при импорте) останется False.
    """
    import database.history_trades_repository as history_trades_repository

    history_trades_repository.history_trades_db = NoOpHistoryTradesDb()

    import bybit_logic.api_algorithms.short_bu_ts_limit_engine as engine_module

    engine_module.USE_DEMO = True


@celery_app.task(
    name="demo_showcase_trade",
    bind=True,
    queue="demo_showcase",
    max_retries=2,
    default_retry_delay=5,
)
def demo_showcase_trade(self, symbol: str) -> dict:
    """Демо-сделка для маркетинга — запускается по тому же сигналу, что реальные подписчики."""
    _force_demo_isolation()

    symbol = symbol.upper()

    if not DEMO_SHOWCASE_API_KEY or not DEMO_SHOWCASE_API_SECRET:
        logger.error("demo_showcase_trade: не заданы DEMO_SHOWCASE_API_KEY/SECRET, пропуск")
        return {"status": "error", "symbol": symbol, "error": "missing_credentials"}

    lock_key = f"trade:demo_showcase:{symbol}"
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    lock = redis_client.lock(lock_key, timeout=_LOCK_TTL_SECONDS, blocking=False)
    if not lock.acquire(blocking=False):
        logger.warning("Дубликат demo_showcase_trade отфильтрован: %s", lock_key)
        return {"status": "skipped_duplicate", "symbol": symbol}

    try:
        from bybit_logic.api_algorithms.short_bu_ts_limit_engine import start_trading

        trade_id = start_trading(
            symbol=symbol,
            tg_id=DEMO_SHOWCASE_TG_ID,
            name=DEMO_SHOWCASE_NAME,
            api_key=DEMO_SHOWCASE_API_KEY,
            api_secret=DEMO_SHOWCASE_API_SECRET,
            sum_for_trades=DEMO_SHOWCASE_USDT_AMOUNT,
        )
    except Exception as e:
        logger.error("Ошибка demo_showcase_trade symbol=%s: %s", symbol, e, exc_info=True)
        raise self.retry(exc=e, countdown=5)
    finally:
        try:
            lock.release()
        except Exception:
            pass

    demo_showcase_trades_db.insert_trade(
        {
            "trade_id": trade_id,
            "symbol": symbol,
            "tg_id": DEMO_SHOWCASE_TG_ID,
            "sum_for_trades": DEMO_SHOWCASE_USDT_AMOUNT,
            "created_at": datetime.utcnow(),
        }
    )
    logger.info("demo_showcase_trade запущена: trade_id=%s symbol=%s", trade_id, symbol)
    return {"status": "started", "symbol": symbol, "trade_id": trade_id}
```

- [ ] **Step 4: Запустить тесты и убедиться, что они проходят**

Run: `python -m unittest tests.test_demo_showcase -v`
Expected: все 5 тестов (`NoOpHistoryTradesDbTests`, `DemoShowcaseIsolationTests`,
3× `DemoShowcaseTaskTests`) — `ok`.

- [ ] **Step 5: Commit**

```bash
git add demo_showcase/tasks.py tests/test_demo_showcase.py
git commit -m "feat: demo_showcase_trade celery task with demo-mode isolation"
```

---

### Task 4: Триггер из `/short_3_limit`

**Files:**
- Create: `demo_showcase/trigger.py`
- Modify: `tests/test_demo_showcase.py`

**Interfaces:**
- Consumes: `demo_showcase.config.DEMO_SHOWCASE_ENABLED: bool` (Task 1),
  `demo_showcase.tasks.demo_showcase_trade` (Celery task, Task 3) — импортируется лениво внутри
  функции
- Produces: `demo_showcase.trigger.maybe_trigger_demo_showcase(symbol: str) -> None`

- [ ] **Step 1: Написать падающие тесты**

Добавить в `tests/test_demo_showcase.py`:

```python
class DemoShowcaseTriggerTests(unittest.TestCase):
    @patch("demo_showcase.trigger.DEMO_SHOWCASE_ENABLED", False)
    def test_disabled_does_not_queue(self):
        from demo_showcase import trigger

        with patch("demo_showcase.tasks.demo_showcase_trade") as mock_task:
            trigger.maybe_trigger_demo_showcase("BTCUSDT")
            mock_task.delay.assert_not_called()

    @patch("demo_showcase.trigger.DEMO_SHOWCASE_ENABLED", True)
    def test_enabled_queues_task_with_symbol(self):
        from demo_showcase import trigger

        with patch("demo_showcase.tasks.demo_showcase_trade") as mock_task:
            trigger.maybe_trigger_demo_showcase("BTCUSDT")
            mock_task.delay.assert_called_once_with(symbol="BTCUSDT")
```

- [ ] **Step 2: Запустить тесты и убедиться, что они падают**

Run: `python -m unittest tests.test_demo_showcase -v`
Expected: `FAIL` / `ERROR` — `ModuleNotFoundError: No module named 'demo_showcase.trigger'`.

- [ ] **Step 3: Реализовать `demo_showcase/trigger.py`**

```python
"""Хук из /short_3_limit: параллельно реальным подписчикам ставит demo-сделку для маркетинга."""
from __future__ import annotations

from demo_showcase.config import DEMO_SHOWCASE_ENABLED
from logger_config import setup_logger

logger = setup_logger(__name__)


def maybe_trigger_demo_showcase(symbol: str) -> None:
    """Не срабатывает, если DEMO_SHOWCASE_ENABLED=false. Иначе ставит Celery-задачу в очередь demo_showcase."""
    if not DEMO_SHOWCASE_ENABLED:
        return

    from demo_showcase.tasks import demo_showcase_trade

    demo_showcase_trade.delay(symbol=symbol)
    logger.info("demo_showcase_trade поставлена в очередь: symbol=%s", symbol)
```

- [ ] **Step 4: Запустить тесты и убедиться, что они проходят**

Run: `python -m unittest tests.test_demo_showcase -v`
Expected: все 7 тестов — `ok`.

- [ ] **Step 5: Commit**

```bash
git add demo_showcase/trigger.py tests/test_demo_showcase.py
git commit -m "feat: demo_showcase trigger hook (gated by DEMO_SHOWCASE_ENABLED)"
```

---

### Task 5: Хук в `/short_3_limit`

**Files:**
- Modify: `server_api/routes/trading.py:22-33` (внутри `short_3_limit_endpoint`)

**Interfaces:**
- Consumes: `demo_showcase.trigger.maybe_trigger_demo_showcase(symbol: str) -> None` (Task 4)

- [ ] **Step 1: Добавить вызов хука**

В `server_api/routes/trading.py`, функция `short_3_limit_endpoint`, сразу после проверки
`if not symbol: raise HTTPException(...)` и **до** `users = await db.list_trading_candidates()`,
добавить (локальный импорт — как и остальные импорты в этой функции, например
`from database.history_trades_repository import history_trades_db` чуть ниже):

Было (`server_api/routes/trading.py:29-35`):
```python
        if not symbol:
            raise HTTPException(status_code=400, detail="Символ не может быть пустым")
        
        users = await db.list_trading_candidates()
```

Стало:
```python
        if not symbol:
            raise HTTPException(status_code=400, detail="Символ не может быть пустым")

        from demo_showcase.trigger import maybe_trigger_demo_showcase

        maybe_trigger_demo_showcase(symbol)

        users = await db.list_trading_candidates()
```

- [ ] **Step 2: Смоук-проверка, что модуль импортируется без ошибок**

Run: `python -c "import server_api.routes.trading"`
Expected: без исключений (пустой вывод).

- [ ] **Step 3: Commit**

```bash
git add server_api/routes/trading.py
git commit -m "feat: hook demo_showcase trigger into /short_3_limit"
```

---

### Task 6: Регистрация очереди `demo_showcase` в Celery

**Files:**
- Modify: `celery_app/celery_config.py`

**Interfaces:**
- Consumes: `demo_showcase.tasks` (модуль с зарегистрированной задачей `demo_showcase_trade`, Task 3)

- [ ] **Step 1: Добавить очередь и модуль импорта**

В `celery_app/celery_config.py`, было:
```python
celery_app.conf.update(
    imports=[
        'celery_app.tasks.short_3_limit',
        'celery_app.tasks.short_3_limit_nomulti',
        'celery_app.tasks.engine_execute_trade',
        'celery_app.tasks.hedge_long_short_bu_ts',
        'celery_app.tasks.custom_algo_nomulti',
        'celery_app.tasks.notifications',
        'celery_app.tasks.subscription_lifecycle',
        'celery_app.tasks.api_key_lifecycle',
        'celery_app.worker_signals',
    ],
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    enable_utc=True,
    timezone='Europe/Moscow',
    broker_connection_retry_on_startup=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    task_queues=(
        Queue("default"),
        Queue("trade_user"),
    ) + _engine_queues,
```

Стало (добавлены `'demo_showcase.tasks'` в `imports` и `Queue("demo_showcase")` в `task_queues`):
```python
celery_app.conf.update(
    imports=[
        'celery_app.tasks.short_3_limit',
        'celery_app.tasks.short_3_limit_nomulti',
        'celery_app.tasks.engine_execute_trade',
        'celery_app.tasks.hedge_long_short_bu_ts',
        'celery_app.tasks.custom_algo_nomulti',
        'celery_app.tasks.notifications',
        'celery_app.tasks.subscription_lifecycle',
        'celery_app.tasks.api_key_lifecycle',
        'celery_app.worker_signals',
        'demo_showcase.tasks',
    ],
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    enable_utc=True,
    timezone='Europe/Moscow',
    broker_connection_retry_on_startup=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    task_queues=(
        Queue("default"),
        Queue("trade_user"),
        Queue("demo_showcase"),
    ) + _engine_queues,
```

- [ ] **Step 2: Проверить, что Celery-приложение поднимается и видит задачу**

Run: `python -c "from celery_app.celery_config import celery_app; print('demo_showcase_trade' in celery_app.tasks)"`
Expected: `True`

- [ ] **Step 3: Commit**

```bash
git add celery_app/celery_config.py
git commit -m "feat: register demo_showcase queue in celery config"
```

---

### Task 7: Документировать переменные в `.env.example`

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Добавить секцию переменных**

В `.env.example`, после блока `SUBSCRIPTION_LIFECYCLE_CHECK_HOURS=12` (перед секцией `# Telegram`),
добавить:

```env
# -----------------------------
# Demo-показ сделок для маркетинга (изолированный Celery-воркер, свой demo Bybit аккаунт)
# -----------------------------
DEMO_SHOWCASE_ENABLED=false
DEMO_SHOWCASE_TG_ID=490882969
DEMO_SHOWCASE_NAME=demo_showcase
DEMO_SHOWCASE_API_KEY=
DEMO_SHOWCASE_API_SECRET=
DEMO_SHOWCASE_USDT_AMOUNT=5000
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: document DEMO_SHOWCASE_* env vars in .env.example"
```

---

### Task 8: Деплой и ручная проверка (Manual/integration — не автоматизируется)

**Files:** нет изменений кода — только серверная конфигурация и ручная верификация.

- [ ] **Step 1: Завести отдельный demo-аккаунт Bybit**

Создать (или использовать выделенный) demo-аккаунт Bybit специально под маркетинг, получить его
API key/secret (Demo Trading в интерфейсе Bybit → API Management).

- [ ] **Step 2: Прописать переменные на сервере**

В серверном `.env` (`/root/multiuser_bot/Scalp_bot/.env` — путь из предыдущего деплоя в этом
проекте):

```env
DEMO_SHOWCASE_ENABLED=true
DEMO_SHOWCASE_API_KEY=<реальный demo API key>
DEMO_SHOWCASE_API_SECRET=<реальный demo API secret>
```

(`DEMO_SHOWCASE_TG_ID`, `DEMO_SHOWCASE_NAME`, `DEMO_SHOWCASE_USDT_AMOUNT` можно оставить по
умолчанию или переопределить сумму под конкретный скриншот.)

**Перед включением:** убедиться, что `tg_id=490882969` НЕ является активным реальным trading
candidate в Mongo `users` (нет реальных ключей, или `stop_trading: true`) — иначе demo- и
real-сессии для этого tg_id столкнутся на общем ключе идемпотентности
`trade_cmd:{tg_id}:{symbol}`.

- [ ] **Step 3: Запустить новый воркер**

В новой screen-сессии (по аналогии с `multi_scalp_engine_0/1`):

```bash
screen -S multi_scalp_demo_showcase
cd /root/multiuser_bot/Scalp_bot
myvenv/bin/celery -A celery_app.celery_config worker -Q demo_showcase --concurrency=1
# Ctrl+A, D — отсоединиться
```

- [ ] **Step 4: Прогнать задачу вручную (без ожидания реального сигнала)**

```bash
myvenv/bin/celery -A celery_app.celery_config call demo_showcase_trade --queue demo_showcase --kwargs '{"symbol": "BTCUSDT"}'
```

Проверить в логах воркера (`screen -r multi_scalp_demo_showcase`):
- сделка открылась на demo-эндпоинте Bybit (не на mainnet — сверить по балансу/интерфейсу demo-аккаунта);
- в Telegram пришло уведомление `tg_id=490882969` в обычном формате (с суммой сделки).

- [ ] **Step 5: Проверить изоляцию от боевой истории/статистики**

После закрытия demo-сделки (или принудительной остановки для теста) убедиться, что:
- в Mongo `history_trades` **нет** новой записи с `tg_id=490882969` за это время;
- `users.statistics` для `tg_id=490882969` **не изменилась**;
- в Mongo `demo_showcase_trades` **появилась** новая запись аудита.

- [ ] **Step 6: Прогнать реальный сигнал через `/short_3_limit` и убедиться, что оба пути сработали**

```bash
curl -X POST http://127.0.0.1:8050/short_3_limit -d 'BTCUSDT'
```

Проверить: реальные подписчики получили сделки как раньше (без регрессии), и параллельно ушла
задача `demo_showcase_trade` (видно в логах роутера/нового воркера).

---

## Self-Review

**Spec coverage:** все разделы спеки (`docs/superpowers/specs/2026-08-11-demo-showcase-trading-design.md`)
покрыты: архитектура — Tasks 1–4; хук в `/short_3_limit` — Task 5; регистрация очереди — Task 6;
"Область действия" (только `/short_3_limit`) — Task 5 трогает только этот эндпоинт; "Безопасность и
изоляция" (USE_DEMO forced + Redis-lock + `if_position_open` inherited) — Task 3; "Хранение истории"
(отдельная коллекция, не history_trades) — Task 2/3; "Деплой" — Task 8; "Тестирование" — Tasks 2–4
(unit) + Task 8 (manual/integration).

**Уточнение к спеке, найденное при планировании:** спека описывала изоляцию от `history_trades`
на уровне намерения ("аудит-запись в отдельную коллекцию... НЕ в history_trades"), но не указывала
механизм. При изучении кода обнаружилось, что `TradeSession` (переиспользуемая без изменений) сама
безусловно пишет в `history_trades`/`users.statistics` через модульный синглтон `history_trades_db`.
Механизм — монки-патч атрибута `database.history_trades_repository.history_trades_db` на no-op
заглушку, выполняемый в собственном изолированном процессе до первого импорта движка (Task 2, 3).
Это не меняет ни одного архитектурного решения из спеки (по-прежнему zero правок в
`short_bu_ts_limit_engine.py`, по-прежнему изоляция на уровне процесса) — только конкретизирует, как
именно спека выполняется технически.

**Placeholder scan:** нет TBD/TODO, нет описаний без кода, каждый шаг с кодом содержит реальный код.

**Type consistency:** `start_trading(symbol, tg_id, name, api_key, api_secret, sum_for_trades) -> str`
используется в Task 3 с теми же именами параметров, что в реальной сигнатуре
(`bybit_logic/api_algorithms/short_bu_ts_limit_engine.py:864`). `maybe_trigger_demo_showcase(symbol: str) -> None`
одинаково объявлена в Task 4 и потреблена в Task 5. `demo_showcase_trade` — имя Celery-задачи
одинаково в Task 3 (`name="demo_showcase_trade"`), Task 4 (`.delay(...)`) и Task 6 (проверка
регистрации).

---

**Plan complete and saved to `docs/superpowers/plans/2026-08-12-demo-showcase-trading.md`.**
