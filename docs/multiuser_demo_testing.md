# Мультиюзер: demo-тест Short 3 limit (2 аккаунта)

Пошаговый сценарий: два demo-аккаунта Bybit, подписка через админ-бота, сигнал на API, проверка Redis и логов.

Предполагается ветка **`feature/bot_multiuser`** и Phase 2 (feed + engine workers).

---

## 1. Подготовка `.env`

```env
USE_DEMO=true
REDIS_URL=redis://:PASSWORD@127.0.0.1:PORT/10
MONGO_URI=mongodb://localhost:27017
MONGO_DB=scalp_bot

TRADE_ENGINE_COUNT=2
MAX_SESSIONS_PER_ENGINE=30
PRICE_FEED_REDIS_ENABLED=true
PRICE_FEED_LOCAL_FALLBACK=true
TRADE_SUBMIT_STAGGER_SEC=0.05
PNL_LOG_INTERVAL=5

# Параметры алгоритма (общие для всех)
TRIGGER_PERCENTAGE=3
TRIGGER_TS_PERCENTAGE=1.0
STOP_LOSS_PERCENTAGE=40
POSITION_SIDE=Sell
COUNT_LIMIT_ORDERS=3
LIMIT_PERCENTAGE=10

TELEGRAM_BOT_TOKEN=...   # бот multiuser (bot.main)
ADMIN_IDS=1395854084,525006772   # доступ к /admin (через запятую)
LOCAL_SERVER_URL=http://127.0.0.1:8050
```

Ключи Bybit **не** кладутся в `.env` для multiuser — они в Mongo у каждого пользователя.

---

## 2. Два demo-пользователя в Mongo

Для каждого тестового Telegram-аккаунта (или двух `tg_id` вручную в Mongo):

| Поле | Значение |
|------|----------|
| `subscription_data.subscription` | `true` |
| `subscription_data.wait_sub_confirmation` | `false` |
| `subscription_data.end_subscription_date` | дата окончания (для авто-напоминаний и отключения, см. [README.md](../README.md)) |
| `bybit_data.api_key` | DEMO API key аккаунта 1 / 2 |
| `bybit_data.api_secret` | DEMO secret |
| `bybit_data.sum_for_trades` | `10`–`20` (USDT на сделку) |
| `bybit_data.stop_trading` | `false` |

Через **админ-бота** (`python -m bot.main`):

1. Оба пользователя пишут `/start` в боте.
2. Оформляют подписку (оплата / ожидание).
3. Админ: **Подписчики** → найти пользователя → подтвердить подписку.
4. Пользователь в **профиле** вводит demo API key / secret и сумму.

---

## 3. Запуск всех сервисов

Из корня проекта, `source myvenv/bin/activate`:

```bash
# T1 — API
python -m server_api.main

# T2 — Price feed (WS только по сигналу)
python -m services.market_price_feed

# T3 — Engine 0
CELERY_ENGINE_ID=0 celery -A celery_app.celery_config worker \
  -Q trade_engine_0 -n engine0@%h --concurrency=1 -l info

# T4 — Engine 1
CELERY_ENGINE_ID=1 celery -A celery_app.celery_config worker \
  -Q trade_engine_1 -n engine1@%h --concurrency=1 -l info

# T5 — Router
celery -A celery_app.celery_config worker -Q default,trade_user --concurrency=4 -l info

# T5b — Celery Beat (подписки; для demo-теста торговли не обязателен, для prod — да)
celery -A celery_app.celery_config beat -l info

# T6 — Бот (админка + профили)
python -m bot.main
```

Проверка:

```bash
curl http://127.0.0.1:8050/health
```

---

## 4. Запуск торговли

Рекомендуется ликвидная монета на **demo**: `BTCUSDT` или `ETHUSDT`.

```bash
curl -X POST http://127.0.0.1:8050/short_3_limit -d "BTCUSDT"
```

Ожидаемый ответ:

```json
{"symbol":"BTCUSDT","status":"started","queued":2,...}
```

`queued: 2` — если оба пользователя прошли фильтр (ключи + подписка + сумма).

---

## 5. Жизненный цикл (как на самом деле в коде)

```
POST /short_3_limit  (TradingView → cloudflare → API)
  ① Mongo: list_trading_candidates() + фильтр → список trade_jobs
  ② если список не пуст: request_feed_symbol → feed открывает WS
  ③ для каждого user: Celery short_3_limit → assign_trade → engine_execute_trade
  → TradeSession: ордера на Bybit → feed_hub.subscribe (ref +1) → цена из Redis
  → закрытие → ref -1 → при ref=0 feed закрывает WS
```

**Важно:** «подписчики» для торговли = пользователи с `subscription_data.subscription=true` в Mongo, **не** коллекция `subscribers` (это рассылка уведомлений в nomulti-боте).

Статический список монет в `.env` **не используется**.

---

## 6. Redis в Docker

Узнай имя контейнера:

```bash
docker ps | grep redis
```

Подключение (подставь пароль/порт из `REDIS_URL`):

```bash
docker exec -it <redis_container> redis-cli -a 'PASSWORD' -p 6379
```

Или с хоста, если порт проброшен (`14571:6379`):

```bash
redis-cli -h 127.0.0.1 -p 14571 -a 'PASSWORD'
```

### Команды во время сделки

```redis
# Статус feed
GET market:feed:status
GET market:feed:symbols

# Сколько сессий читают цену по BTC
GET market:feed:ref:BTCUSDT

# Последняя цена
GET market:last:BTCUSDT

# Нагрузка engine
GET engine:0:load
GET engine:1:load
GET engine:0:alive

# Idempotency (активная сделка tg_id+symbol)
KEYS trade_cmd:*
```

### Смотреть тики в реальном времени

```bash
redis-cli -h 127.0.0.1 -p 14571 -a 'PASSWORD' SUBSCRIBE market:ticker:BTCUSDT
```

После открытия сделки должны пойти JSON-сообщения с `price`.

---

## 7. Где смотреть логи

| Где | Что искать |
|-----|------------|
| **T2 feed** | `Started primary WS for BTCUSDT`, `Stopped WS streams` |
| **T3/T4 engine** | `engine_execute_trade`, `📊 [tg_id:BTCUSDT] цена \| % \| PnL` |
| **T5 router** | `short_3_limit routed`, `engine_id` |
| **T1 API** | `short_3_limit enqueued`, `queued=N` |
| **Файлы** | каталог `logs/` (если настроен `logger_config`) |

Строка PnL в engine (каждые `PNL_LOG_INTERVAL` сек):

```text
📊 [123456789:BTCUSDT] 95000.5 | +0.12% | +0.05 USDT
```

`123456789` — `tg_id` пользователя: по нему видно, **какой аккаунт** торгует.

Telegram:

- **Каждому пользователю** — лично при закрытии позиции (`send_notification_to_user_task`).
- **Подписчикам** (коллекция `subscribers`, nomulti-бот) — «алгоритм запущен»; для чистого multiuser-теста это может не срабатывать, если никто не подписан на рассылку.

---

## 8. На что обратить внимание

| Проверка | Ожидание |
|----------|----------|
| `queued` в API | = число пользователей с ключами |
| `engine:*:load` | растёт на 1 за сделку, падает после закрытия |
| `market:feed:ref:BTCUSDT` | = число активных сессий на BTC |
| Feed лог | WS открылся после сигнала, закрылся после последнего закрытия |
| Bybit demo | у каждого пользователя своя позиция на своих ключах |
| Дубликат | второй сигнал по той же монете для того же `tg_id` — skip (idempotency) |
| `stop_trading` в Mongo | пользователь пропускается в API |

---

## 9. Остановка

`POST /stop_trading_by_symbol` с ключами из **`.env`** — не закрывает позиции пользователей. Закрывать вручную на Bybit demo или дождаться SL/алгоритма.

---

## 10. Unit-тесты без Bybit

```bash
python -m unittest tests.test_trade_orchestrator tests.test_redis_market_keys \
  tests.test_dual_feed_failover tests.test_redis_price_subscriber \
  tests.test_symbol_session_ref -v
```
