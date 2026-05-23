# Активация виртуального окружения

* python -m venv myvenv
* source myvenv/bin/activate

# Запуск сервера Scalp_api

* python -m server_api.main

# Запуск Celery Worker

Рекомендуется для async short-алгоритмов (один `AsyncTradeEngine` на процесс):

```bash
celery -A celery_app.celery_config worker --loglevel=info -Q default,trade_user --concurrency=1
```

При `--concurrency>1` каждый prefork-процесс поднимает свой движок и свой набор WebSocket — растёт RAM.

# Запуск Telegram бота (мультиюзер)

* python -m bot.main

# Запуск Telegram бота (немультюзер)

* `python -m bot_nomultiuser.main` (из корня репозитория; в `.env` — `TELEGRAM_BOT_TOKEN`, `LOCAL_SERVER_URL`)

# Новый алгоритм: Hedge Long+Short (немультюзер)

Добавлен алгоритм одновременного открытия `Long` и `Short` по одному символу в hedge-режиме Bybit:

- Файл алгоритма: `bybit_logic/api_algorithms/hedge_long_short_bu_ts.py`
- Плечо: `10x` на обе стороны
- Начальный стоп-лосс: `2%` на каждую сторону
- БУ (безубыток): при `+2%` по каждой стороне отдельно
- Трейлинг-стоп: шаг `1%` по каждой стороне отдельно
- Логика работы ног независимая: если одна нога уже закрыта, вторая продолжает отдельно обрабатывать БУ/трейлинг и не блокируется.
- В логах добавлены явные сообщения при достижении порога БУ и при каждой попытке установки БУ/активации трейлинга.

## Запуск через API + Celery

| Эндпоинт | Кто торгует | Движок | Celery-задача |
|----------|-------------|--------|----------------|
| `POST /short_3_limit` | все подписчики с ключами (multiuser) | **Async** | `short_3_limit` |
| `POST /nomulti_short_3_limit` | один аккаунт из `.env` | **Async** | `nomulti_short_3_limit` |
| `POST /hedge_long_short_bu_ts` | один аккаунт из `.env` | Sync | `hedge_long_short_bu_ts` |
| `POST /nomulti_custom_algo` | один аккаунт + JSON-конфиг | Sync | `nomulti_custom_algo` |

Тело для short/hedge: **сырой текст** символа, например `BTCUSDT`.  
Custom: JSON (`symbol`, `tg_id`, опционально `order_amount_override`).

Немультюзерный бот (`bot_nomultiuser`) → `/nomulti_short_3_limit`, `/hedge_long_short_bu_ts`, `/nomulti_custom_algo`.

Для работы нужны: API, Celery worker, **Redis** (broker + idempotency/snapshots async-движка), MongoDB (подписчики, custom-конфиг).

---

# Архитектура торговых движков (May 2026)

## Что обновлено на async

Перенесены на **единый async-движок** (`short_bu_ts_limit_engine.py`):

| Сценарий | Было | Стало |
|----------|------|--------|
| Multiuser short (`/short_3_limit`) | sync, глобальные переменные, **свой WebSocket на каждую Celery-задачу/процесс** | `AsyncTradeEngine` + `MarketFeedHub` |
| Nomulti short (`/nomulti_short_3_limit`) | sync `short_bu_ts_limit.py`, блокировка воркера на всю сделку | `start_trading_nomulti()` → тот же async-движок |

**Не переведены на async** (пока sync, воркер занят до конца сделки):

- `hedge_long_short_bu_ts.py` — две ноги long/short в hedge;
- `custom_algo_nomulti.py` — настраиваемый алгоритм из Mongo.

Старая sync multiuser-реализация сохранена для отката/сравнения:  
`bybit_logic/api_algorithms/_legacy/short_bu_ts_limit_multiuser_sync.py`.

Удалён дублирующий эндпоинт `POST /nomulti_short_bu_ts_limit` (логика совпадала с `nomulti_short_3_limit`).

## Как работает async-движок

**Модуль:** `bybit_logic/api_algorithms/short_bu_ts_limit_engine.py`  
**Точки входа:**

- multiuser: `short_bu_ts_limit_multiuser.start_trading(...)` → `submit_trade(...)` → сразу `trade_id`;
- nomulti: `start_trading_nomulti(symbol)` — ключи и сумма из `.env`, `tg_id` из `NOMULTI_TG_ID` / `ADMIN_CHAT_ID`.

**Компоненты:**

1. **`AsyncTradeEngine`** — singleton в процессе Celery: daemon-thread + `asyncio` event loop.
2. **`TradeSession`** — одна изолированная сделка (состояние в `TradeState`, без globals).
3. **`MarketFeedHub`** (`bybit_logic/feeds/hybrid_feed_hub.py`) — цена из **Redis Pub/Sub** (центральный feed); при `feed:down` — local WS на символ в процессе engine.
4. **`BybitHttpAdapter`** — вызовы pybit через `asyncio.to_thread` (не блокируют loop).
5. **`TradeStateStore` (Redis)** — idempotency `trade_cmd:{tg_id}:{symbol}`; snapshots состояния для recovery.

**Цепочка при сигнале `/short_3_limit` (Phase 2):**

1. FastAPI читает символ, для каждого подписчика ставит `short_3_limit` (с `stagger`).
2. `short_3_limit` → `trade_orchestrator.assign_trade()` → `engine_execute_trade` на очередь `trade_engine_{id}`.
3. Engine worker (`CELERY_ENGINE_ID`, `concurrency=1`, max 30 сессий) → `submit_trade` → `TradeSession`.
4. Цена: при `subscribe` → refcount в Redis → feed открывает WS на символ → `market:ticker:{SYMBOL}`; при `feed:down` — local WS в engine.
5. При `%` БУ → trailing stop (`bybit_logic/bybit_func/trailing_stop.py`).
6. При закрытии → `history_trades`, Telegram, `unsubscribe`, refcount 0 → feed закрывает WS.

**Логи по аккаунту:** в терминале engine worker — строки `📊 [tg_id:SYMBOL] …` (интервал `PNL_LOG_INTERVAL` в `.env`).

**Demo-тест multiuser:** [docs/multiuser_demo_testing.md](docs/multiuser_demo_testing.md)

**Nomulti** — та же логика, один `tg_id` и ключи из `.env`.

## Зачем async (результаты бенчмарка)

На VPS 2 CPU / ~4 GB RAM, 10 параллельных demo-сделок:

| Режим | RAM бота | CPU пик (система) |
|-------|----------|-------------------|
| 10 sync-процессов | ~1280 MB | ~100% |
| 10 async-сессий (1 процесс) | ~143 MB | ~50% |

При **100 подписчиках на один символ**: один WS на монету в **feed** (пока есть активные сессии), не 100 WS.

Нагрузочные тесты: `tests/load/short_bu_ts_limit_async_benchmark.py`, `tests/load/short_bu_ts_limit_multiprocess_benchmark.py`.

## Phase 2: Redis feed + engine sharding

Подробно: **[docs/phase2_scaling.md](docs/phase2_scaling.md)**

| Сервис | Команда |
|--------|---------|
| Price feed | `python -m services.market_price_feed` |
| Engine worker i | `CELERY_ENGINE_ID=i celery … worker -Q trade_engine_i --concurrency=1` |
| Router | `celery … worker -Q default,trade_user` |

- `TRADE_ENGINE_COUNT` — число engine-очередей (в `.env`, для тестов 2, для прода ~34).
- `MAX_SESSIONS_PER_ENGINE=30` — лимит сделок на процесс.
- Бенчмарк шардирования: `python -m tests.load.phase2_sharding_benchmark --sessions 60 --mode orchestrator`

## Требования к инфраструктуре

- **Redis** — broker Celery, idempotency, snapshots, price Pub/Sub, orchestrator load.
- **Feed process** — `python -m services.market_price_feed` (отдельно от Celery).
- **Engine workers** — по одному на `trade_engine_{i}`, `--concurrency=1`.
- **Router worker** — `default`, `trade_user` (hedge/custom).
- `worker_prefetch_multiplier=1` в `celery_app/celery_config.py`.

## Остановка торговли

- `POST /stop_trading_by_symbol`, `POST /stop_trading_all` — закрытие через **ключи из `.env`** (`USE_DEMO`).
- Для multiuser это не останавливает сессии на ключах пользователей автоматически; сессии сами вызывают `stop_trading_by_symbol` при `size=0` или при ручном закрытии на бирже.

## Файлы (шпаргалка)

| Назначение | Путь |
|------------|------|
| Async-движок (prod) | `bybit_logic/api_algorithms/short_bu_ts_limit_engine.py` |
| Multiuser API-обёртка | `bybit_logic/api_algorithms/short_bu_ts_limit_multiuser.py` |
| Sync multiuser (legacy) | `bybit_logic/api_algorithms/_legacy/short_bu_ts_limit_multiuser_sync.py` |
| Sync nomulti (бенчмарк) | `bybit_logic/api_algorithms/short_bu_ts_limit.py` |
| Hedge sync | `bybit_logic/api_algorithms/hedge_long_short_bu_ts.py` |
| Custom sync | `bybit_logic/api_algorithms/custom_algo_nomulti.py` |
| Celery multiuser router | `celery_app/tasks/short_3_limit.py` |
| Celery engine execute | `celery_app/tasks/engine_execute_trade.py` |
| Orchestrator | `celery_app/trade_orchestrator.py` |
| Price feed service | `services/market_price_feed/` |
| Celery nomulti short | `celery_app/tasks/short_3_limit_nomulti.py` |

# Последние изменения (Apr 2026)

## Торговая логика и плечо

- Унифицирована установка плеча в `bybit_logic/bybit_func/position.py` (`set_leverage`).
- Добавлена обработка ограничений биржи по `maxLeverage`:
  - по умолчанию действует **строгий режим**: если запрошенное плечо выше лимита инструмента, позиция не открывается;
  - подписчикам отправляется уведомление, что вход отменен из-за ограничения плеча;
  - в `set_leverage` оставлен флаг `allow_lower_if_exceeds_max=True` для опционального гибкого режима (автоснижение плеча) в будущих сценариях.

## Hedge: защита второй ноги (fail-safe)

В `bybit_logic/api_algorithms/hedge_long_short_bu_ts.py` добавлена аварийная логика:

- штатно БУ + трейлинг включаются при достижении `+2%` по соответствующей ноге;
- дополнительно, если одна нога закрылась, для второй (если она еще открыта) принудительно запускается каскадная установка БУ и активация трейлинга;
- это снижает риск сценария, когда обе ноги закрываются по стартовому SL без активации защиты.

## Уведомления по hedge-сделке

Добавлены более детальные сообщения подписчикам:

- отдельное уведомление по открытию `Long`;
- отдельное уведомление по открытию `Short`;
- уведомления по переводу в БУ для каждой ноги;
- отдельные уведомления по закрытию `Long` и `Short`;
- итоговое сообщение при закрытии обеих ног.

## Ретраи отправки уведомлений

- В `bot/utils/helpers.py` для массовой рассылки добавлены ретраи (`до 3 попыток` на пользователя) с небольшим backoff.
- В `celery_app/tasks/notifications.py` для персональных уведомлений также добавлен внутренний retry-цикл.
- Это уменьшает долю сбоев вида `Timeout` при отправке сообщений в Telegram.

# Последние изменения (May 2026)

## Миграция short-алгоритмов на AsyncTradeEngine

- Prod multiuser и nomulti short используют `short_bu_ts_limit_engine.py` (см. раздел «Архитектура торговых движков»).
- Celery-задачи short больше не блокируют воркер на всю сделку — только постановка в движок.
- Исправлена сериализация `datetime` в Redis-snapshots (`closed_position_info`).
- Единый nomulti-эндпоинт для бота и сигналов: `/nomulti_short_3_limit`.

## Custom Algo для `bot_nomultiuser`

Добавлен настраиваемый алгоритм для немультюзерного бота с хранением конфигурации в Mongo.

### Что появилось в Telegram UI

- В главном меню добавлена кнопка `🔴 Custom Algo`.
- В ветке `Трейдинг -> Алгоритмы` добавлена кнопка `Custom ⚙️`.
- Добавлен мастер настройки конфигурации:
  - выбор стороны (`лонг/шорт`);
  - включение/выключение `Trailing Stop`, `Stop Loss`, `БУ`;
  - сумма сделки в USDT (можно не фиксировать и вводить при запуске).
- Если конфиг уже сохранен, в `Custom ⚙️` показывается текущая конфигурация и кнопки `Изменить` / `Назад`.
- Если в конфиге не задана сумма, при запуске через `🔴 Custom Algo` бот спрашивает сумму для текущего запуска.

### Новые backend-компоненты

- Репозиторий конфигурации:
  - `database/custom_algo_repository.py`
  - Коллекция Mongo: `custom_algo_configs`
  - Поля: `direction`, `use_trailing_stop`, `trailing_activate_pct`, `trailing_step_pct`, `use_stop_loss`, `stop_loss_pct`, `use_breakeven`, `breakeven_pct`, `order_amount_usdt`, `updated_at`.
- API schema:
  - `server_api/schemas.py` -> `CustomAlgoLaunchRequest`.
- API endpoint:
  - `POST /nomulti_custom_algo` в `server_api/routes/trading.py`.
- Celery task:
  - `celery_app/tasks/custom_algo_nomulti.py` (`nomulti_custom_algo`).
- Регистрация task в Celery:
  - `celery_app/celery_config.py`.
- Алгоритм:
  - `bybit_logic/api_algorithms/custom_algo_nomulti.py`.

### Поведение Custom-алгоритма

- Алгоритм открывает позицию по выбранной стороне (`Buy` для long, `Sell` для short).
- `SL`, `БУ`, `TS` работают опционально по флагам конфигурации.
- `Trailing Stop` поддерживает независимую активацию (отдельный `% активации`) и шаг обновления (`% шага`).
- Если сумма сделки не сохранена в конфиге, используется `order_amount_override` из шага запуска.
- Для совместимости с текущей логикой расчета оставлен костыль: в расчете qty используется `user_amount * 10`.

### Формат результата позиции

- В ветке информации о позиции используется сообщение:
  - `✅ Информация о позиции получена!`
  - далее текст из `bybit_logic/bybit_func/position.py::result_position_info(...)`:
    `Позиция`, `Статус`, `Сторона`, `Размер`, `Цена входа/выхода`, `Открыта/Закрыта`, `PnL`, `Изменение`.

## Обновления алгоритмов (May 2026)

### Раздельные суммы USDT для nomulti алгоритмов

Ранее `short_bu_ts_limit` и `hedge_long_short_bu_ts` использовали общий `USDT_AMOUNT`.
Теперь суммы разделены:

- `short_bu_ts_limit`:
  - `SHORT_BU_TS_LIMIT_USDT_AMOUNT`
  - fallback: `USDT_AMOUNT`
- `hedge_long_short_bu_ts`:
  - `HEDGE_USDT_AMOUNT`
  - fallback: `USDT_AMOUNT`

Это позволяет настраивать размер позиции отдельно для каждого алгоритма, сохраняя обратную совместимость со старым `.env`.

### Short BU TS limit: БУ после 3 усреднений

В `bybit_logic/api_algorithms/short_bu_ts_limit.py` добавлена динамика порога БУ:

- до 3 сработавших усреднений порог БУ берется из `TRIGGER_PERCENTAGE`;
- после 3-го усреднения порог БУ автоматически становится `1.0%`.

Усреднение фиксируется по факту увеличения размера позиции (`size` вырос после срабатывания лимитного ордера).

Трейлинг-стоп продолжает включаться только после успешной установки БУ (как и раньше).
Порог немедленной установки первого трейлинг-стопа также пересчитывается от активного порога БУ по правилу `БУ + 1%`.

## Конфиг окружения (May 2026)

### Внутренний и публичный URL API

Теперь внутри проекта разделены URL для внутренних вызовов и публичного отображения:

- `LOCAL_SERVER_URL` — используется ботами и админ-проверками для вызова API внутри проекта;
- `SERVER_URL` — публичный URL для уведомлений при старте сервера (список доступных endpoint'ов).

Рекомендуемый сценарий:

- `LOCAL_SERVER_URL=http://127.0.0.1:8050`
- `SERVER_URL=https://<ваш-публичный-url>`

Это убирает ошибки, когда бот случайно отправляет внутренние запросы на внешний туннель.

### Mongo env-ключи: поддержка старых и новых имен

`config.py` поддерживает оба формата:

- новый: `MONGO_URI`, `MONGO_DB`
- legacy: `MONGODB_URI`, `MONGODB_DB`

Приоритет: сначала `MONGO_*`, затем `MONGODB_*`.

### Единый параметр режима маржи

Добавлен единый параметр:

- `MARGIN_MODE=CROSS` или `MARGIN_MODE=ISOLATED`

Он применяется централизованно в алгоритмах через `position.set_account_margin_mode(...)` перед установкой плеча.
По умолчанию используется `CROSS`.