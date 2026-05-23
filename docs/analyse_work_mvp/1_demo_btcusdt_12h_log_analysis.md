# MVP multiuser: анализ логов demo-сессии BTCUSDT (~12 ч)

Обзор по реальному прогону **Phase 2** (`feature/bot_multiuser`): два пользователя, одна монета, Bybit Demo.  
Сигнал ~**11:13**, наблюдение логов до ~**23:24** (22.05.2026).

---

## 1. Контекст запуска

| Компонент | Статус |
|-----------|--------|
| API (`server_api.main`) | Up, Cloudflare URL в `.env` |
| Feed (`services.market_price_feed`) | Up, `redis_secure` Docker |
| Engine 0 / 1 | Celery `trade_engine_0/1`, `--concurrency=1` |
| Router | Celery `default,trade_user` |
| Redis | `127.0.0.1:14571`, DB `/10` |
| Бот | `python -m bot.main`, тестовый токен в `misc.py` |

Пользователи в Mongo (торговая подписка + demo-ключи):

| tg_id | Имя | Сумма (профиль) | Engine |
|-------|-----|-----------------|--------|
| `1395854084` | Dushe4kaaa | 100 USDT | 0 |
| `5032415442` | SHIFYuu | 150 USDT | 1 |

Третий кандидат из Mongo **пропущен**: `skipped_no_keys=1`.

---

## 2. Цепочка сигнала (подтверждено логами)

```
curl POST /short_3_limit "BTCUSDT"
    │
    ├─ API: list_trading_candidates() → 2 trade_jobs
    ├─ API: request_feed_symbol(BTCUSDT)  ← ДО Celery
    ├─ Feed: market:feed:ensure → primary + backup WS
    │
    └─ Router: short_3_limit ×2
           ├─ tg 1395854084 → assign → trade_engine_0
           └─ tg 5032415442 → assign → trade_engine_1
                  └─ engine_execute_trade → TradeSession (demo API)
```

**API (T10):**

```text
Feed WS requested for BTCUSDT before enqueue (2 user(s))
short_3_limit enqueued … queued=2 skipped_no_keys=1
```

**Router (T14):**

```text
short_3_limit routed … tg_id=1395854084 engine=0 trade_id=1395854084:BTCUSDT:…
short_3_limit routed … tg_id=5032415442 engine=1 trade_id=5032415442:BTCUSDT:…
```

**Feed (T11):**

```text
Started primary WS for BTCUSDT
Started backup WS for BTCUSDT
```

Вывод: orchestrator, порядок «Mongo → WS → Celery» и sharding **2 user → 2 engine** работают как задумано.

---

## 3. Работа сделок в течение ~12 часов

### 3.1 Engine-логи (PnL)

Оба engine каждые ~2 с ( `PNL_LOG_INTERVAL=2` ):

```text
📊 [tg_id:BTCUSDT] цена | +0.48–0.50% | +PnL USDT
```

| tg_id | PnL USDT (пример) | Интерпретация |
|-------|-------------------|---------------|
| 1395854084 | ~+4.5–4.7 | Short в небольшом плюсе |
| 5032415442 | ~+7.2–7.4 | Short в плюсе (больше сумма в профиле) |

Цена BTC ~77667–77681 — тики из Redis feed поступали, цикл алгоритма **не останавливался**.

Позиции **не закрылись** за 12 ч: не сработали пороги выхода из `.env` (`TRIGGER_PERCENTAGE=3`, трейлинг, SL 40% и т.д.) — для длинного demo это ожидаемо.

### 3.2 Feed: WS и failover

После старта feed держал **два** WS (primary + backup) на `wss://stream.bybit.com/v5/public/linear`.

Периодически:

```text
ping/pong timed out
Failover: active publisher primary -> backup
Failover: active publisher backup -> primary
```

**Не критично:** dual feed переключал источник, сервис не падал, WS на BTCUSDT оставался активным.

### 3.3 Engine: redis ↔ local fallback

Около **23:22** на **обоих** engine:

```text
MarketFeedHub mode switch: redis -> local
… ~30 сек …
MarketFeedHub mode switch: local -> redis
```

Причина: `PRICE_FEED_LOCAL_FALLBACK=true` — если тики в Redis «протухли» (`PRICE_FEED_STALE_SEC` / `FEED_DOWN_SEC`), engine временно поднимает **свой** WS. Отсюда дополнительные `ping/pong` в логах engine.

Цикл PnL **продолжился** — fallback отработал штатно.

### 3.4 Bybit Demo API

Единичные ошибки:

```text
api-demo.bybit.com Read timed out
Error getting positions: Connection aborted
```

Разовые сетевые таймауты; сессии не завершились, логи PnL шли дальше.

### 3.5 Celery: missed heartbeat

Router (T14) ~19:48 и ~20:21:

```text
missed heartbeat from engine0@…
missed heartbeat from engine1@…
```

Типично при: сон Mac, долгая одна задача `engine_execute_trade` (12 ч при `--concurrency=1`). **Сделки при этом жили** (логи в 23:22 есть). Это предупреждение мониторинга Celery, не обязательный обрыв trade.

---

## 4. Уведомления Telegram (проблема и исправление)

### 4.1 Что было в логах router

При старте алгоритмов:

```text
send_notification … Начало синхронной рассылки сообщения 1 подписчикам
```

Два engine → **две** задачи `send_notification` → оба текста «🚀 Алгоритм запущен!» ушли **одному** получателю из Mongo-коллекции **`subscribers`** (legacy nomulti), а не в `users`.

| Кто | Что получил |
|-----|-------------|
| `5032415442` | Оба сообщения (свой + чужой), т.к. единственный в `subscribers` |
| `1395854084` | Ничего на старт |

Торговая подписка (`users.subscription_data.subscription`) с рассылкой **`subscribers` не связана**.

### 4.2 Что уже исправлено в коде

В `short_bu_ts_limit_engine.py` все события идут через `_notify_user` → `send_notification_to_user_task(tg_id)`:

1. Ошибка плеча  
2. Дубликат позиции  
3. Ошибка открытия ордера (новое)  
4. Алгоритм запущен  
5. Позиция закрыта  

В `notifications.py` для личных сообщений: токен `CELERY_TRADING_BOT_TOKEN` → `TEST_TELEGRAM_BOT_TOKEN` → `TELEGRAM_BOT_TOKEN`.

**После рестарта engine/router** каждый пользователь получает только свои события в бота, с которым писал `/start`.

---

## 5. Сводная таблица «что работает»

| Область | Результат |
|---------|-----------|
| Webhook `/short_3_limit` | OK |
| Фильтр Mongo (ключи, подписка) | OK, 2/3 |
| WS feed по символу (dynamic ensure) | OK |
| Redis price → engine | OK |
| 2 независимые сессии на demo-ключах | OK, ~12 ч |
| Orchestrator (engine 0/1) | OK |
| Dual feed failover | OK, с шумом в логах |
| Hybrid local fallback | OK |
| Broadcast уведомления multi | **Был баг** → исправлено на per-tg_id |

---

## 6. Рекомендации после анализа

1. **Перезапустить** engine + router после правок уведомлений.  
2. В `.env`: `USE_DEMO=true`; при тест-боте — `CELERY_TRADING_BOT_TOKEN` = `TEST_TELEGRAM_BOT_TOKEN`.  
3. **Не усыплять Mac** на длинных demo или принять `missed heartbeat` / WS reconnect.  
4. Для проверки feed во время сделки:
   ```bash
   redis-cli -h 127.0.0.1 -p 14571 -a '…' GET market:feed:ref:BTCUSDT
   redis-cli -h 127.0.0.1 -p 14571 -a '…' GET market:feed:status
   ```
5. Закрытие позиций: алгоритм (SL/БУ/TS) или вручную на Bybit Demo; `stop_trading_by_symbol` в API — только по ключам из `.env`, не по всем multi-пользователям.

---

## 7. Источники логов (терминалы)

| T | Сервис | Ключевые маркеры |
|---|--------|------------------|
| T10 | API | `Feed WS requested`, `queued=2` |
| T11 | market_price_feed | `Started primary/backup WS`, `Failover` |
| T12 | engine 0 | `1395854084:BTCUSDT`, `redis -> local` |
| T13 | engine 1 | `5032415442:BTCUSDT` |
| T14 | router | `short_3_limit routed`, `send_notification` |

---

## 8. Вывод одной строкой

**MVP Phase 2 multiuser на demo подтверждён:** один сигнал → общий feed на BTCUSDT → две изолированные сделки на двух аккаунтах ~12 часов с устойчивостью к сбоям WS/Redis; единственная функциональная ошибка UX — broadcast уведомлений вместо личных — устранена в engine.

См. также: [start_demo_test.md](../../start_demo_test.md), [multiuser_demo_testing.md](../multiuser_demo_testing.md), [phase2_scaling.md](../phase2_scaling.md).
