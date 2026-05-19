# Phase 2: масштабирование (Redis price hub + Celery engine sharding)

## Обзор

Фаза 2 добавляет:

1. **Центральный price feed** — два WebSocket (primary/backup) → Redis Pub/Sub.
2. **Engine workers** — Celery-очереди `trade_engine_0` … `trade_engine_{N-1}`, `concurrency=1`, до **30** активных сделок на процесс.
3. **Local WS fallback** — если оба feed недоступны (`market:feed:status=down`), каждый engine-процесс поднимает свой WebSocket на символ (до 30 сессий делят один WS).

## Компоненты

| Компонент | Путь | Роль |
|-----------|------|------|
| Dual feed service | `services/market_price_feed/` | Primary/backup WS → Redis |
| Redis keys | `bybit_logic/feeds/redis_market_keys.py` | Каналы и статусы |
| Price subscriber | `bybit_logic/feeds/redis_price_subscriber.py` | Подписка engine на тики |
| Hybrid hub | `bybit_logic/feeds/hybrid_feed_hub.py` | Redis + local fallback |
| Trade engine | `bybit_logic/api_algorithms/short_bu_ts_limit_engine.py` | AsyncTradeEngine |
| Orchestrator | `celery_app/trade_orchestrator.py` | Распределение load |
| Router task | `celery_app/tasks/short_3_limit.py` | assign → engine queue |
| Execute task | `celery_app/tasks/engine_execute_trade.py` | submit_trade в воркере |

## Поток сигнала

```
POST /short_3_limit
  → short_3_limit (queue trade_user)
      → orchestrator.assign_trade()  # INCR engine:{id}:load
      → engine_execute_trade → queue trade_engine_{id}
  → engine worker (CELERY_ENGINE_ID=id, concurrency=1)
      → AsyncTradeEngine.submit_trade()
      → TradeSession (цена из Redis или local WS)
  → при закрытии: DECR load, Telegram
```

## Redis

### Цена

- `PUBLISH market:ticker:BTCUSDT` — JSON `{symbol, price, ts, source}`
- `GET market:last:BTCUSDT` — последняя цена (TTL 120s)
- `GET market:feed:status` — `ok` | `degraded` | `down`
- `GET market:feed:active` — `primary` | `backup`

### Orchestrator

- `engine:ids` — SET зарегистрированных engine
- `engine:{id}:load` — активные сделки
- `engine:{id}:alive` — heartbeat воркера
- `engine:pending` — очередь при переполнении

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `TRADE_ENGINE_COUNT` | 2 | Число engine-очередей |
| `MAX_SESSIONS_PER_ENGINE` | 30 | Лимит сделок на процесс |
| `CELERY_ENGINE_ID` | — | ID engine (обязателен на engine-воркере) |
| `PRICE_FEED_REDIS_ENABLED` | true | Читать цену из Redis |
| `PRICE_FEED_LOCAL_FALLBACK` | true | Local WS при feed down |
| `PRICE_FEED_STALE_SEC` | 5 | Stale тик feed |
| `PRICE_FEED_DOWN_SEC` | 15 | Оба feed down |
| `TRADE_SUBMIT_STAGGER_SEC` | 0.03 | Пауза между enqueue в API |
| `MARKET_FEED_SYMBOLS` | BTCUSDT,... | Символы для feed service |

## Запуск (production-like)

### 1. Redis

```bash
redis-server
```

### 2. Market price feed

```bash
python -m services.market_price_feed
```

### 3. Engine workers (пример TRADE_ENGINE_COUNT=2)

```bash
CELERY_ENGINE_ID=0 celery -A celery_app.celery_config worker -Q trade_engine_0 -n engine0@%h --concurrency=1 -l info
CELERY_ENGINE_ID=1 celery -A celery_app.celery_config worker -Q trade_engine_1 -n engine1@%h --concurrency=1 -l info
```

### 4. Router + API tasks

```bash
celery -A celery_app.celery_config worker -Q default,trade_user --concurrency=4 -l info
```

### 5. API

```bash
python -m server_api.main
```

Для ~1000 пользователей: `TRADE_ENGINE_COUNT=34` (34×30=1020 слотов).

## Failover цены

1. **Primary WS** публикует в Redis.
2. Primary stale → **backup** становится active publisher.
3. Primary восстанавливается → через hysteresis может снова стать active.
4. Оба stale → `market:feed:status=down` → engine включает **local WS** на символ.

## Troubleshooting

| Симптом | Действие |
|---------|----------|
| Все сделки `queued` | Запустить engine workers, проверить `engine:{id}:alive` |
| `load` завис после crash | `reaper_stale_engines()` или перезапуск воркера |
| Нет тиков | Проверить `python -m services.market_price_feed`, Redis |
| Rate limit Bybit | Увеличить `TRADE_SUBMIT_STAGGER_SEC` |

## Тесты и бенчмарки

См. [tests/load/README.md](../tests/load/README.md).

```bash
python -m unittest tests.test_trade_orchestrator tests.test_redis_market_keys tests.test_dual_feed_failover
python -m tests.load.phase2_sharding_benchmark --sessions 60 --mode orchestrator
```
