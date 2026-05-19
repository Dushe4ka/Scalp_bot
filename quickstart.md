# Quickstart — Scalp_bot

Два режима проекта и **две ветки** на GitHub:

| Ветка | Режим | Short-алгоритм |
|--------|--------|----------------|
| `feature/bot_multiuser` | Мультиюзер + Phase 2 | Orchestrator, Redis feed, engine workers |
| `feature/bot_nomultiuser` | Немультиюзер (async без Phase 2) | Один Celery worker, без sharding |

Оба режима используют **один API** (`server_api`), **Redis**, **MongoDB**.  
Подробности Phase 2: [docs/phase2_scaling.md](docs/phase2_scaling.md).

---

## 0. Клонирование и ветка

```bash
git clone https://github.com/Dushe4ka/Scalp_bot.git
cd Scalp_bot
```

**Мультиюзер (Phase 2, масштабирование):**

```bash
git fetch origin
git checkout feature/bot_multiuser
```

**Немультиюзер (один аккаунт, проще деплой):**

```bash
git fetch origin
git checkout feature/bot_nomultiuser
```

---

## 1. Общая подготовка (обе ветки)

### Python и зависимости

```bash
python3 -m venv myvenv
source myvenv/bin/activate   # Windows: myvenv\Scripts\activate
pip install -r requirements.txt
```

### Инфраструктура

Нужны **Redis** и **MongoDB** (локально или на VPS):

```bash
# пример локально (macOS Homebrew)
brew services start redis
brew services start mongodb-community
```

Проверка Redis:

```bash
redis-cli ping
# PONG
```

### Файл `.env`

```bash
cp .env.example .env
```

Отредактируй `.env`. Минимум для любого режима:

| Переменная | Назначение |
|------------|------------|
| `REDIS_URL` | Celery broker + orchestrator + idempotency |
| `MONGO_URI`, `MONGO_DB` | Пользователи / custom / history |
| `TELEGRAM_BOT_TOKEN` | Бот (свой токен для multi и nomulti) |
| `LOCAL_SERVER_URL` | `http://127.0.0.1:8050` для локального API |
| `USE_DEMO` | `true` — demo Bybit, `false` — mainnet |
| `DEMO_API_KEY`, `DEMO_API_SECRET` | Ключи demo (для тестов и nomulti) |

Полный список Phase 2 — в `.env.example` (`TRADE_ENGINE_COUNT`, `MAX_SESSIONS_PER_ENGINE`, feed и т.д.).

### Unit-тесты (быстрая проверка после установки)

```bash
python -m unittest tests.test_trade_orchestrator \
  tests.test_redis_market_keys \
  tests.test_dual_feed_failover \
  tests.test_redis_price_subscriber -v
```

На ветке `feature/bot_nomultiuser` тесты orchestrator/Phase 2 могут отсутствовать — пропусти их или переключись на `feature/bot_multiuser`.

---

# Мультиюзерная версия (`feature/bot_multiuser`)

## Что это

- Много пользователей в **MongoDB** (`users`): у каждого свои Bybit-ключи и сумма.
- Сигнал `POST /short_3_limit` → отдельная сделка на **каждого** подписчика с активной подпиской и ключами.
- Telegram: `python -m bot.main` (подписки, профиль, админка). Торговля обычно через **webhook / TradingView** на API, не из меню бота.

## Дополнительные переменные `.env`

```env
TRADE_ENGINE_COUNT=2
MAX_SESSIONS_PER_ENGINE=30
PRICE_FEED_REDIS_ENABLED=true
PRICE_FEED_LOCAL_FALLBACK=true
TRADE_SUBMIT_STAGGER_SEC=0.03
MARKET_FEED_SYMBOL_IDLE_SEC=3600
```

Для ~1000 одновременных short: `TRADE_ENGINE_COUNT=34` (34×30=1020 слотов) и столько же engine-воркеров.

## Запуск сервисов (7 терминалов на локальной машине)

Из корня проекта, venv активирован.

**Терминал 1 — API**

```bash
python -m server_api.main
```

Проверка: `curl http://127.0.0.1:8050/health`

**Терминал 2 — Price feed (центральная цена в Redis)**

```bash
python -m services.market_price_feed
```

При старте feed **не подключается ни к одной монете**.

WS открывается, когда первая сделка **подписалась на цену** (`feed_hub.subscribe` → `ref` 0→1 → `market:feed:ensure`).  
WS закрывается, когда **последняя** сделка по символу закрылась (`ref` 1→0 → `market:feed:release`).

Проверка (Redis; для Docker см. [docs/multiuser_demo_testing.md](docs/multiuser_demo_testing.md)):

```bash
redis-cli GET market:feed:status
redis-cli GET market:feed:ref:BTCUSDT
redis-cli SUBSCRIBE market:ticker:BTCUSDT
```

**Терминалы 3–4 — Engine workers** (по числу `TRADE_ENGINE_COUNT`, пример для 2)

```bash
CELERY_ENGINE_ID=0 celery -A celery_app.celery_config worker \
  -Q trade_engine_0 -n engine0@%h --concurrency=1 -l info
```

```bash
CELERY_ENGINE_ID=1 celery -A celery_app.celery_config worker \
  -Q trade_engine_1 -n engine1@%h --concurrency=1 -l info
```

**Терминал 5 — Router** (маршрутизация short + hedge/custom)

```bash
celery -A celery_app.celery_config worker \
  -Q default,trade_user --concurrency=4 -l info
```

**Терминал 6 — Telegram-бот (опционально для админки)**

```bash
python -m bot.main
```

## Запуск торговли (multi)

Сигнал на символ (тело запроса — только тикер):

```bash
curl -X POST http://127.0.0.1:8050/short_3_limit -d "BTCUSDT"
```

В ответе: `queued` — сколько задач поставлено в Celery.

Цепочка:

```
/short_3_limit → short_3_limit (trade_user) → assign_trade → engine_execute_trade (trade_engine_N)
→ AsyncTradeEngine → цена из Redis (или local WS при feed down)
```

## Подготовка пользователей в Mongo

Пользователь должен иметь:

- `subscription_data.subscription: true`
- `bybit_data.api_key`, `bybit_data.api_secret`
- `bybit_data.sum_for_trades` > 0
- `bybit_data.stop_trading` не `true`

Иначе он будет пропущен при `/short_3_limit`.

## Demo-тест: 2 аккаунта Bybit

Полная инструкция: **[docs/multiuser_demo_testing.md](docs/multiuser_demo_testing.md)**

Кратко:

1. Два пользователя в боте с **demo** API keys в профиле, подписка подтверждена админом.
2. Поднять все 6 сервисов (API, feed, 2×engine, router, bot).
3. `curl -X POST http://127.0.0.1:8050/short_3_limit -d "BTCUSDT"`.
4. Смотреть логи **engine** (`📊 [tg_id:SYMBOL]`), **feed** (`Started/Stopped WS`), Redis (`market:feed:ref:BTCUSDT`).

## Логи торговли по аккаунтам

| Источник | Формат |
|----------|--------|
| Engine worker (T3/T4) | `📊 [tg_id:BTCUSDT] цена \| % \| PnL USDT` — каждые `PNL_LOG_INTERVAL` сек |
| Engine | `engine_execute_trade: engine=… tg_id=… symbol=…` |
| Router | `short_3_limit routed: … engine_id=…` |
| Feed | `Started primary WS for SYMBOL` / `Stopped WS streams` |
| Файлы | `logs/<module>.log` |

Telegram: закрытие позиции — **личное** сообщение на `tg_id` пользователя.

## Остановка

```bash
curl -X POST http://127.0.0.1:8050/stop_trading_by_symbol \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSDT"}'
```

Закрывает позиции по **ключам из `.env`** (`USE_DEMO`), не по ключам всех пользователей автоматически.

## Диагностика Phase 2

```bash
redis-cli GET engine:0:load
redis-cli GET engine:1:load
redis-cli GET engine:0:alive
redis-cli GET market:feed:status
redis-cli LLEN engine:pending
```

| Симптом | Причина |
|---------|---------|
| `queued` в ответе, сделок нет | Не запущены `trade_engine_*` workers |
| `engine:pending` растёт | Все engine заполнены (30×N) |
| Нет цены | Не запущен `services.market_price_feed` |

---

# Немультиюзерная версия (`feature/bot_nomultiuser`)

## Что это

- **Один** торговый аккаунт: ключи и сумма из `.env`.
- Бот с меню: `python -m bot_nomultiuser.main`.
- Short: `POST /nomulti_short_3_limit`.
- Hedge / Custom: sync-алгоритмы на очереди `trade_user` (без engine sharding).

На этой ветке **нет** Phase 2 (orchestrator, feed service, `trade_engine_*`). Достаточно **одного** Celery worker.

## Дополнительные переменные `.env`

```env
# Ключи (при USE_DEMO=true — DEMO_*)
API_KEY=...
API_SECRET=...
DEMO_API_KEY=...
DEMO_API_SECRET=...

SHORT_BU_TS_LIMIT_USDT_AMOUNT=10
# или USDT_AMOUNT=10

NOMULTI_TG_ID=123456789
ADMIN_CHAT_ID=123456789
NOMULTI_USER_NAME=nomulti

USE_DEMO=true
```

`NOMULTI_TG_ID` — куда приходят персональные уведомления о сделке (закрытие, ошибка плеча).

## Запуск сервисов (4 терминала)

**Терминал 1 — API**

```bash
python -m server_api.main
```

**Терминал 2 — Celery** (один worker на все задачи)

```bash
celery -A celery_app.celery_config worker \
  -l info -Q default,trade_user --concurrency=1
```

`--concurrency=1` — один async-движок в процессе, до 30 сессий внутри него (как в Phase 1).

**Терминал 3 — Telegram-бот**

```bash
python -m bot_nomultiuser.main
```

**Price feed и engine workers на этой ветке не нужны** для short.

## Использование из бота

1. `/start` → подписка на оповещения (коллекция `subscribers` в Mongo).
2. Меню торговли:
   - **Short 3 limit (nomulti)** → `POST /nomulti_short_3_limit`
   - **Hedge long + short** → `POST /hedge_long_short_bu_ts`
   - **Custom Algo** → настройка в Mongo `custom_algo_configs`, запуск `POST /nomulti_custom_algo`

## Ручной запуск short

```bash
curl -X POST http://127.0.0.1:8050/nomulti_short_3_limit -d "BTCUSDT"
```

## Уведомления (nomulti)

| Событие | Кому |
|---------|------|
| Старт short, дубликат | Все из Mongo `subscribers` (кто нажал «Подписаться» в nomulti-боте) |
| Закрытие позиции, ошибка плеча | `NOMULTI_TG_ID` / `ADMIN_CHAT_ID` |
| Hedge | Рассылка `subscribers` |

Для рассылки из Celery токен бота должен совпадать с ботом подписки (`TELEGRAM_BOT_TOKEN` или `CELERY_SUBSCRIBERS_BOT_TOKEN`).

---

# Немульти на ветке `feature/bot_multiuser` (Phase 2)

Если работаешь на **multi**-ветке, но нужен только nomulti short — **тот же стек**, что и для multi (feed + engine + router). В боте вызывается `/nomulti_short_3_limit`, дальше orchestrator → `engine_execute_trade`, как у multiuser short.

Запуск бота:

```bash
python -m bot_nomultiuser.main
```

Инфраструктура — как в разделе «Мультиюзерная версия» выше.

---

# Бенчмарки и тесты

Подробнее: [tests/load/README.md](tests/load/README.md).

## Unit-тесты (Phase 2, ветка `feature/bot_multiuser`)

```bash
python -m unittest tests.test_trade_orchestrator \
  tests.test_redis_market_keys \
  tests.test_dual_feed_failover \
  tests.test_redis_price_subscriber -v
```

## Phase 2 — orchestrator (без Bybit, только Redis)

Проверяет распределение `engine:*:load` при 30/60 виртуальных assign. **Redis обязателен.**

```bash
export TRADE_ENGINE_COUNT=2
export MAX_SESSIONS_PER_ENGINE=30

python -m tests.load.phase2_sharding_benchmark --sessions 30 --mode orchestrator
python -m tests.load.phase2_sharding_benchmark --sessions 60 --mode orchestrator
```

Отчёты:

- `tests/load/reports/phase2_orchestrator_30.txt`
- `tests/load/reports/phase2_orchestrator_60.txt`

Ожидание для 60 при 2 engine: `assigned: 60`, нагрузка ~30+30, `Sharding OK: True`.

Дополнительно:

```bash
python -m tests.load.short_bu_ts_limit_async_benchmark \
  --sessions 10 --minutes 1 --via-orchestrator
```

Только assign через orchestrator, без реальной торговли.

## Phase 2 — demo (полный путь через Celery)

Нужны: `.env` с `DEMO_API_KEY`, `DEMO_API_SECRET`, `USE_DEMO=true`, запущенные **feed + 2 engine + router** (см. раздел multi выше).

```bash
python -m tests.load.phase2_sharding_benchmark \
  --sessions 30 \
  --mode demo \
  --minutes 3 \
  --stagger 0.2
```

Отчёт: `tests/load/reports/phase2_sharding_30.txt` (loads, `market:feed:status`, PID engine workers).

Для 60 сессий:

```bash
python -m tests.load.phase2_sharding_benchmark --sessions 60 --mode demo --minutes 5 --stagger 0.2
```

## Phase 1 — async, один процесс (сравнение RAM)

Обходит orchestrator, напрямую `AsyncTradeEngine` (demo keys):

```bash
python -m tests.load.short_bu_ts_limit_async_benchmark \
  --sessions 10 \
  --minutes 5 \
  --stagger 0.3
```

Отчёт: `tests/load/reports/short_bu_ts_limit_async_benchmark.txt`

## Legacy — sync, N процессов

```bash
python -m tests.load.short_bu_ts_limit_multiprocess_benchmark \
  --processes 10 \
  --minutes 5
```

## Порядок для прогона Phase 2 demo

1. Redis
2. `python -m services.market_price_feed`
3. `CELERY_ENGINE_ID=0` … `trade_engine_0`
4. `CELERY_ENGINE_ID=1` … `trade_engine_1`
5. Router: `celery … -Q default,trade_user`
6. Бенчмарк из корня проекта

Проверка во время прогона:

```bash
watch -n 2 'redis-cli GET engine:0:load; redis-cli GET engine:1:load; redis-cli GET market:feed:status'
```

---

# Сводка: что запускать

| Компонент | Multi (`bot_multiuser`) | Nomulti (`bot_nomultiuser`) |
|-----------|-------------------------|-----------------------------|
| API | да | да |
| Redis | да | да |
| MongoDB | да | да |
| `market_price_feed` | да (short) | нет |
| `trade_engine_*` workers | да (short) | нет |
| Celery `trade_user` router | да | да (один worker) |
| `bot.main` | опционально | — |
| `bot_nomultiuser.main` | опционально | да |

---

# Частые проблемы

| Проблема | Решение |
|----------|---------|
| Бот не достучался до API | `LOCAL_SERVER_URL` / `SERVER_URL` = адрес API |
| Celery не берёт задачи | Redis, worker слушает нужные очереди |
| Short multi не торгует | Запущены engine workers + feed |
| Нет Telegram | `TELEGRAM_BOT_TOKEN`, Celery worker для `notifications` |
| Rate limit Bybit | Увеличить `TRADE_SUBMIT_STAGGER_SEC` |

---

# Полезные ссылки

- [docs/phase2_scaling.md](docs/phase2_scaling.md) — архитектура Phase 2
- [docs/multiuser_demo_testing.md](docs/multiuser_demo_testing.md) — demo-тест 2 пользователей
- [tests/load/README.md](tests/load/README.md) — бенчмарки
- [README.md](README.md) — обзор async-движка
