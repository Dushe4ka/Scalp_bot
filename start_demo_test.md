# Demo multi — запуск (`feature/bot_multiuser`)

Чеклист запуска **мультиюзер** на **Bybit Demo**. Ключи торговли — в Mongo (demo API key/secret из профиля бота). В `.env` обязательно: `USE_DEMO=true`.

**Redis** — в **Docker Desktop** (не Homebrew). Celery, feed и orchestrator подключаются по `REDIS_URL` из `.env`.

---

## 0. Один раз: проект и ветка

```bash
cd "/Users/pavelgolubinec/Desktop/MyProjects/Основные проекты/Scalp_bot"

git fetch origin
git checkout feature/bot_multiuser

python3 -m venv myvenv
source myvenv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # если .env ещё нет — отредактируй ниже
```

---

## 1. `.env` для demo (мульти)

Минимум:

```env
USE_DEMO=true

# Redis — контейнер redis_secure (Docker Desktop), 127.0.0.1:14571
REDIS_URL=redis://:ВАШ_ПАРОЛЬ@127.0.0.1:14571/10
RESULT_BACKEND=redis://:ВАШ_ПАРОЛЬ@127.0.0.1:14571/10

MONGO_URI=mongodb://127.0.0.1:27017
MONGO_DB=scalp_bot
# или legacy:
# MONGODB_URI=mongodb://127.0.0.1:27017/
# MONGODB_DB=scalp_bot

LOCAL_SERVER_URL=http://127.0.0.1:8050
SERVER_URL=https://ваш-туннель.trycloudflare.com   # для webhook / TradingView

TELEGRAM_BOT_TOKEN=...          # боевой бот (если без тестового)
TEST_TELEGRAM_BOT_TOKEN=...     # тестовый бот — см. bot/utils/misc.py
ADMIN_CHAT_ID=...
ADMIN_IDS=...

# Celery шлёт уведомления через TELEGRAM_BOT_TOKEN, не через TEST_*
# Чтобы уведомления шли в тестового бота:
# CELERY_SUBSCRIBERS_BOT_TOKEN=<тот же токен, что TEST_TELEGRAM_BOT_TOKEN>

TRADE_ENGINE_COUNT=2
MAX_SESSIONS_PER_ENGINE=30
PRICE_FEED_REDIS_ENABLED=true
PRICE_FEED_LOCAL_FALLBACK=true
TRADE_SUBMIT_STAGGER_SEC=0.05
MARKET_FEED_SYMBOL_IDLE_SEC=3600

TRIGGER_PERCENTAGE=3
TRIGGER_TS_PERCENTAGE=1.0
STOP_LOSS_PERCENTAGE=40
POSITION_SIDE=Sell
COUNT_LIMIT_ORDERS=3
LIMIT_PERCENTAGE=10
PNL_LOG_INTERVAL=5
```

**Multi / demo:**

- Сделки `/short_3_limit` — **ключи из Mongo** у каждого пользователя (demo keys в профиле).
- `USE_DEMO=true` — запросы к **demo API Bybit**.
- `DEMO_API_KEY` в `.env` для multi не обязателен (нужен для `stop_trading_*` и nomulti).

---

## 2. Инфраструктура

### 2.1 Redis — Docker Desktop (`redis_secure`)

1. Запусти **Docker Desktop** (статус Running).
2. Контейнер **`redis_secure`** должен быть в состоянии **Running** (Containers → ▶ Start).

Проверка, что контейнер поднят:

```bash
docker ps --format "table {{.Names}}\t{{.Ports}}" | grep -i redis
```

Ожидаемый вывод:

```text
redis_secure   127.0.0.1:14571->14571/tcp
```

| Параметр | Значение |
|----------|----------|
| Имя контейнера | `redis_secure` |
| Хост | `127.0.0.1` |
| Порт (с Mac и внутри контейнера) | `14571` |
| Проброс | `127.0.0.1:14571 → 14571/tcp` |
| База в `.env` | `/10` (номер DB в URL) |

В `.env` всегда **`127.0.0.1:14571`** — не `6379` (у этого образа Redis слушает 14571).

**Ping с Mac** (пароль из `.env`):

```bash
redis-cli -h 127.0.0.1 -p 14571 -a 'ВАШ_ПАРОЛЬ' ping
# PONG
```

Или URL как в `REDIS_URL`:

```bash
redis-cli -u "redis://:ВАШ_ПАРОЛЬ@127.0.0.1:14571/10" ping
```

**Изнутри контейнера:**

```bash
docker exec -it redis_secure redis-cli -p 14571 -a 'ВАШ_ПАРОЛЬ' ping
```

**Alias** (удобно для §6–7):

```bash
export REDIS_CLI='redis-cli -h 127.0.0.1 -p 14571 -a ВАШ_ПАРОЛЬ'
# $REDIS_CLI GET market:feed:status
```

Если нет `PONG` — Celery и feed не подключатся. Сверь пароль в `.env` с паролем контейнера `redis_secure`.

### 2.2 MongoDB

Локально (пример macOS):

```bash
brew services start mongodb-community
```

Или свой инстанс — главное, чтобы `MONGO_URI` / `MONGODB_URI` совпадал с реальным адресом.

```bash
mongosh --eval "db.adminCommand('ping')"
```

---

## 3. Порядок запуска (алгоритм)

### 3.1 До торговли — один раз

| # | Что | Действие |
|---|-----|----------|
| 1 | Код | §0: venv, ветка `feature/bot_multiuser` |
| 2 | Конфиг | §1: `.env`, `USE_DEMO=true`, `REDIS_URL` → `redis_secure:14571` |
| 3 | Redis | Docker Desktop → контейнер **`redis_secure`** Running → `PONG` |
| 4 | Mongo | `mongosh` ping, пользователи с demo-ключами (§4) |
| 5 | Бот (опционально раньше) | **T6** `python -m bot.main` — подписки и ключи в профиле |

### 3.2 Каждый сеанс — порядок сервисов (6 терминалов)

Запускай **строго после** Redis + Mongo. Рекомендуемая последовательность:

```
① T2  Price feed     → слушает Redis market:feed:ensure / release
② T3  Engine 0       → очередь trade_engine_0
③ T4  Engine 1       → очередь trade_engine_1
④ T5  Router         → default + trade_user (short_3_limit → orchestrator)
⑤ T1  API            → POST /short_3_limit, webhook
⑥ T6  Telegram-бот   → профили (если ещё не запущен)
```

Почему так: feed и engine должны быть готовы **до** сигнала, иначе нет цены в Redis и некому выполнить `engine_execute_trade`. Router — до API, чтобы принять `short_3_limit` из Celery.

**Минимум перед `curl`:** T2 + T3 + T4 + T5 + T1 работают; T6 нужен для настройки пользователей, не для самого webhook.

### 3.3 Что происходит при сигнале (алгоритм торговли)

Источник: TradingView / `curl` → `POST /short_3_limit` (тело = символ, например `BTCUSDT`).

```
POST /short_3_limit
    │
    ├─① Mongo: list_trading_candidates()
    │      фильтр: ключи, stop_trading, sum_for_trades > 0
    │      → список trade_jobs (или пусто → стоп)
    │
    ├─② Если есть кого торговать:
    │      request_feed_symbol → Redis market:feed:ensure
    │      → feed открывает WS Bybit → тики в market:ticker:SYMBOL
    │
    └─③ Для каждого пользователя (stagger):
           Celery short_3_limit (очередь trade_user)
               → assign_trade (orchestrator, слот engine 0..N-1)
               → engine_execute_trade (очередь trade_engine_K)
                   → AsyncTradeEngine / TradeSession:
                       плечо → market short → лимитки → SL
                       → feed_hub.subscribe (ref +1)
                       → цикл по цене из Redis
                       → закрытие → ref -1 → при ref=0 feed закрывает WS
```

Краткая цепочка Celery:

```
/short_3_limit → short_3_limit (trade_user) → assign_trade → engine_execute_trade (trade_engine_N)
→ цена из Redis (или local WS, если feed down)
```

**Кто «подписчик» для торговли:** пользователи Mongo `users` с `subscription_data.subscription=true` и demo-ключами в профиле — **не** коллекция `subscribers` (она для рассылок nomulti).

---

## 4. Пользователи в боте (demo-ключи)

| Поле | Значение |
|------|----------|
| `subscription_data.subscription` | `true` |
| `bybit_data.api_key` | demo API key |
| `bybit_data.api_secret` | demo secret |
| `bybit_data.sum_for_trades` | `10`–`20` (в движке qty ≈ сумма × 10) |
| `bybit_data.stop_trading` | не `true` |

Через `python -m bot.main` (тестовый токен в `bot/utils/misc.py`):

1. `/start` → подписка  
2. Админ → **Подписчики** → подтвердить  
3. Профиль → demo key / secret и сумма  

---

## 5. Запуск сервисов — 6 терминалов

Порядок запуска — **§3.2** (`T2 → T3 → T4 → T5 → T1 → T6`). Команды:

В **каждом** терминале:

```bash
cd "/Users/pavelgolubinec/Desktop/MyProjects/Основные проекты/Scalp_bot"
source myvenv/bin/activate
```

| Терминал | Команда |
|----------|---------|
| **T1 — API** | `python -m server_api.main` |
| **T2 — Price feed** | `python -m services.market_price_feed` |
| **T3 — Engine 0** | `CELERY_ENGINE_ID=0 celery -A celery_app.celery_config worker -Q trade_engine_0 -n engine0@%h --concurrency=1 -l info` |
| **T4 — Engine 1** | `CELERY_ENGINE_ID=1 celery -A celery_app.celery_config worker -Q trade_engine_1 -n engine1@%h --concurrency=1 -l info` |
| **T5 — Router** | `celery -A celery_app.celery_config worker -Q default,trade_user --concurrency=4 -l info` |
| **T6 — Бот** | `python -m bot.main` |

При `TRADE_ENGINE_COUNT=3` добавь воркер с `-Q trade_engine_2` и `CELERY_ENGINE_ID=2`.

В логах Celery должно быть: `Connected to redis://:**@127.0.0.1:14571/10` (ваш порт/DB).

---

## 6. Проверка

```bash
curl http://127.0.0.1:8050/health

# Redis (Docker, с хоста)
redis-cli -h 127.0.0.1 -p 14571 -a 'ВАШ_ПАРОЛЬ' GET market:feed:status
redis-cli -h 127.0.0.1 -p 14571 -a 'ВАШ_ПАРОЛЬ' GET engine:0:load
redis-cli -h 127.0.0.1 -p 14571 -a 'ВАШ_ПАРОЛЬ' GET engine:1:load
```

Feed при старте **не** открывает WS — только после сигнала с открытыми сделками.

---

## 7. Запуск сделок

После §3.2 и §6:

```bash
curl -X POST http://127.0.0.1:8050/short_3_limit -d "BTCUSDT"
```

Ответ: `"queued": N` — сколько пользователей прошли фильтр. Подробная цепочка — **§3.3**.

После сигнала:

```bash
redis-cli -h 127.0.0.1 -p 14571 -a 'ВАШ_ПАРОЛЬ' GET market:feed:ref:BTCUSDT
redis-cli -h 127.0.0.1 -p 14571 -a 'ВАШ_ПАРОЛЬ' SUBSCRIBE market:ticker:BTCUSDT
```

---

## 8. Логи

| Терминал | Что искать |
|----------|------------|
| API | `Feed WS requested`, `queued=…` |
| Feed | `Started primary WS for BTCUSDT` |
| Engine 0/1 | `engine_execute_trade`, `📊 [tg_id:BTCUSDT]` |
| Router | `short_3_limit routed` |
| Telegram | закрытие — личное на `tg_id` |

Файлы: `logs/*.log`

---

## 9. Webhook (TradingView / Cloudflare)

```http
POST https://ВАШ_ДОМЕН/short_3_limit
Content-Type: text/plain

BTCUSDT
```

`SERVER_URL` в `.env` = тот же публичный URL.

---

## 10. Остановка

```bash
curl -X POST http://127.0.0.1:8050/stop_trading_by_symbol \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSDT"}'
```

Закрывает только по ключам из `.env`, не по всем пользователям multi.

---

## Сводка

| Шаг | Действие |
|-----|----------|
| 0–1 | venv, `.env`, `USE_DEMO=true` |
| 2 | `redis_secure` + Mongo |
| 3.2 | **T2 → T3 → T4 → T5 → T1 → T6** (см. алгоритм) |
| 4 | Пользователи с demo-ключами в Mongo |
| 7 | `curl -X POST …/short_3_limit -d "BTCUSDT"` |

Подробнее: [docs/multiuser_demo_testing.md](docs/multiuser_demo_testing.md) · Phase 2: [docs/phase2_scaling.md](docs/phase2_scaling.md)

---

## Частые проблемы (Redis Docker)

| Симптом | Решение |
|---------|---------|
| Celery `Cannot connect to redis` | Docker не запущен / `redis_secure` stopped / в URL не `127.0.0.1:14571` |
| `NOAUTH` | Пароль в URL: `redis://:password@host:port/db` |
| `redis-cli ping` без `-a` не работает | Добавь `-h 127.0.0.1 -p <host_port> -a 'password'` |
| Старые задачи в очереди при старте router | Нормально: отработают `send_notification` из Redis; для чистого старта — flush DB (осторожно) |
