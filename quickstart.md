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

### Клонирование на сервер ветки `feature/bot_multiuser`

#### Вариант 1 — клон сразу нужной ветки (рекомендуется, быстрее)

```bash
git clone --branch feature/bot_multiuser --single-branch \
  https://github.com/Dushe4ka/Scalp_bot.git Scalp_bot

cd Scalp_bot
git status
git log -1 --oneline
```

#### Вариант 2 — полный клон + переключение

```bash
git clone https://github.com/Dushe4ka/Scalp_bot.git
cd Scalp_bot
git fetch origin feature/bot_multiuser
git checkout feature/bot_multiuser
git pull origin feature/bot_multiuser
```

#### Вариант 3 — через SSH (если на сервере настроен ключ)

```bash
git clone --branch feature/bot_multiuser --single-branch \
  git@github.com:Dushe4ka/Scalp_bot.git Scalp_bot
cd Scalp_bot
```

#### Вариант 4 — клон через токен (HTTPS, приватный репозиторий)

```bash
git clone --branch feature/bot_multiuser --single-branch \
  https://<GITHUB_USERNAME>:<GITHUB_TOKEN>@github.com/Dushe4ka/Scalp_bot.git Scalp_bot
cd Scalp_bot
```

> Замените `<GITHUB_USERNAME>` и `<GITHUB_TOKEN>` (Personal Access Token с правом `repo`).

#### После клонирования (стандартные шаги)

```bash
cd Scalp_bot

python3 -m venv myvenv
source myvenv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
nano .env

git branch --show-current
git log -1 --oneline
```

В `.env` для VPS:

```env
LOCAL_SERVER_URL=http://127.0.0.1:8050
SERVER_URL=https://ваш-url.trycloudflare.com
```

`LOCAL_SERVER_URL` — всегда локальный. `SERVER_URL` — публичный URL туннеля (для TradingView и уведомлений API).

#### Обновление на сервере позже

```bash
cd Scalp_bot
git fetch origin
git pull origin feature/bot_multiuser
source myvenv/bin/activate
pip install -r requirements.txt   # если менялись зависимости
pm2 restart scalp-api scalp-bot    # после pull
```

---

## Деплой на сервер — шпаргалка запуска

Краткий чеклист (7 процессов). Подробности PM2/screen — ниже в разделе мультиюзера.

| # | Где | Сервис |
|---|-----|--------|
| 1 | PM2 | API (`scalp-api`) |
| 2 | PM2 | Price feed (`scalp-feed`) |
| 3 | screen | Engine worker 0 |
| 4 | screen | Engine worker 1 |
| 5 | screen | Router worker |
| 6 | screen (опц.) | Celery Beat |
| 7 | PM2 | Telegram-бот (`scalp-bot`) |
| 8 | screen | **Cloudflare Tunnel** (webhook TradingView) |

**PM2 — API**

```bash
pm2 start ./myvenv/bin/python --name scalp-api -- -m server_api.main
```

**PM2 — Price feed (центральная цена в Redis)**

```bash
pm2 start ./myvenv/bin/python --name scalp-feed -- -m services.market_price_feed
```

**screen — Engine worker 0**

```bash
CELERY_ENGINE_ID=0 celery -A celery_app.celery_config worker \
  -Q trade_engine_0 -n engine0@%h --concurrency=1 -l info
```

**screen — Engine worker 1**

```bash
CELERY_ENGINE_ID=1 celery -A celery_app.celery_config worker \
  -Q trade_engine_1 -n engine1@%h --concurrency=1 -l info
```

**screen — Router worker**

```bash
celery -A celery_app.celery_config worker \
  -Q default,trade_user --concurrency=4 -l info
```

**screen — Celery Beat** (подписки и API-ключи, один процесс)

```bash
celery -A celery_app.celery_config beat -l info
```

**PM2 — Telegram-бот**

```bash
pm2 start ./myvenv/bin/python --name scalp-bot -- -m bot.main
```

### Cloudflare Tunnel (webhook TradingView)

Quick tunnel для приёма сигналов с TradingView. Держите процесс **всегда запущенным** в отдельной screen-сессии.

```bash
screen -S cloudflare
cloudflared tunnel --url http://127.0.0.1:8050 --protocol http2 --edge-ip-version 4
# Ctrl+A, D — отсоединиться (туннель продолжит работать)
```

В логе появится URL вида `https://xxxx.trycloudflare.com`:

1. Пропишите в `.env`: `SERVER_URL=https://xxxx.trycloudflare.com`
2. `pm2 restart scalp-api`
3. В TradingView укажите webhook: `https://xxxx.trycloudflare.com/short_3_limit`, тело алерта —
   `{{ticker}} SHORT SIGNAL` (обычная сделка) или `{{ticker}} Short1` (повышенный риск — тейк 1%,
   стоп 10%, без усреднений; см. [«Запуск торговли (multi)»](#запуск-торговли-multi))

Проверка:

```bash
curl https://xxxx.trycloudflare.com/health
curl -X POST "https://xxxx.trycloudflare.com/short_3_limit" -d "BTCUSDT"
```

> `--protocol http2 --edge-ip-version 4` стабильнее на VPS, где QUIC (UDP) обрывается.  
> URL `trycloudflare.com` **меняется** при каждом новом запуске — для продакшена используйте [named tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/) с постоянным доменом.

Вернуться к логам туннеля:

```bash
screen -r cloudflare
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
| `RECOMMENDED_TRADE_AMOUNT_PERCENT` | Лимит суммы сделки для обычных пользователей: % от futures-баланса (по умолчанию `1.75`) |
| `SUBSCRIPTION_PRICE_USD` | Цена подписки на 1 месяц в USD (по умолчанию `79`) |
| `BREAKEVEN_AFTER_AVERAGING_COUNT` | После N усреднений меняется порог безубытка (по умолчанию `4`) |
| `TRIGGER_PERCENTAGE_AFTER_AVERAGING` | БУ после N-го усреднения, % (по умолчанию `1.0`) |
| `ADMIN_IDS` | Админы бота; при старте автоматически попадают в whitelist лимита суммы сделки |
| `SUBSCRIPTION_LIFECYCLE_CHECK_HOURS` | Интервал Beat: подписки + срок API-ключей (по умолчанию `12`) |

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
- В **личном кабинете** при наличии API key/secret синхронизируется срок действия ключа с Bybit; показывается «осталось N дней» (если ключ без IP whitelist).
- **Оплата подписки:** экран с QR и адресом кошелька (`URL_PAYMENT`) → ID платежа → «✅ Всё верно» → уведомление админу.
- **Админка:** подтверждение/отклонение из уведомления или раздела «Ожидающие подтверждения»; кнопки действий содержат `tg_id` в callback (не зависят от FSM).
- Админ при подтверждении/отклонении оплаты отправляет пользователю уведомление в Telegram (с кнопкой «Личный кабинет» или «Техподдержка»).
- **Лимит суммы сделки:** обычным пользователям нельзя выставить сумму выше `RECOMMENDED_TRADE_AMOUNT_PERCENT` от баланса; админы и пользователи из whitelist (`app_settings`) — расширенный режим.

## Оплата подписки (пользователь → админ)

1. Пользователь: «Оформить подписку» → **фото с QR** + адрес `URL_PAYMENT` (TRC-20).
2. Оплата по **адресу кошелька** или **QR-коду** на изображении.
3. «Оплатил» → ввод ID платежа → «✅ Всё верно».
4. После подтверждения: в Mongo `wait_sub_confirmation=true`, админам уходит сообщение с ID и кнопкой профиля.
5. Админ: «Подтвердить подписку» / «Отклонить запрос» (из уведомления или админки).
6. Пользователю приходит:
   - подтверждение → текст + кнопка **👤 Личный кабинет** (`profile_menu`);
   - отклонение → текст + кнопка **💬 Техподдержка** (`URL_TECH_SUPPORT`).

**Настройка в `.env`:**

```env
URL_PAYMENT=TWuu1YRatdhMWWxU5cow5Dye9vuQnbRuuK
SUBSCRIPTION_PRICE_USD=79
```

**Файлы:** QR — `_images/qr_code_pay.png`; код — `bot/utils/payment_screen.py`, `bot/handlers/subscription.py`.

## Лимит суммы сделки

1. Пользователь указывает API key/secret в профиле.
2. В настройках «Сумма сделки» бот показывает лимит: `баланс × (RECOMMENDED_TRADE_AMOUNT_PERCENT / 100)`.
3. Ввод выше лимита отклоняется (для whitelist — только предупреждение о риске).

**Whitelist в MongoDB** (`app_settings`):

```json
{ "_id": "trade_amount_unlimited_tg_ids", "tg_ids": [123456789, ...] }
```

- При старте `python -m bot.main` все ID из `ADMIN_IDS` добавляются в `tg_ids` без дубликатов.
- Админка → Подписчики → карточка пользователя → «Разрешить сумму без лимита» / «Вернуть лимит суммы».

Код: `database/app_settings_repository.py`, `bot/utils/trade_amount.py`.

## Дополнительные переменные `.env`

```env
TRADE_ENGINE_COUNT=2
MAX_SESSIONS_PER_ENGINE=30
PRICE_FEED_REDIS_ENABLED=true
PRICE_FEED_LOCAL_FALLBACK=true
TRADE_SUBMIT_STAGGER_SEC=0.03
MARKET_FEED_SYMBOL_IDLE_SEC=3600
SUBSCRIPTION_LIFECYCLE_CHECK_HOURS=12
```

Для ~1000 одновременных short: `TRADE_ENGINE_COUNT=34` (34×30=1020 слотов) и столько же engine-воркеров.

## Запуск сервисов (7+ терминалов на локальной машине)

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

**Терминал 5b — Celery Beat** (проверка подписок каждые 12 ч: напоминания за 3/1 день, отключение по истечении)

```bash
celery -A celery_app.celery_config beat -l info
```

Интервал задаётся в `.env`: `SUBSCRIPTION_LIFECYCLE_CHECK_HOURS=12`.  
Задача `check_subscription_lifecycle` выполняется на **router**-воркере (очередь `default`). Там же — `check_api_key_lifecycle`. Beat должен быть **один** процесс на весь кластер.

**Терминал 6 — Telegram-бот (опционально для админки)**

```bash
python -m bot.main
```

### PM2 — Python-сервисы (API, feed, бот)

Удобно на VPS: автоперезапуск, логи, `pm2 save` после ребута.

Перед первым запуском — из **корня проекта** (где лежат `server_api/`, `bot/`, `myvenv/`):

```bash
cd ~/multiuser_bot/Scalp_bot   # свой путь к проекту
```

Аргументы `-m ...` передаются Python **после `--`**, иначе PM2 ищет файл `server_api.main`.

**Старт (3 процесса)**

```bash
pm2 start ./myvenv/bin/python --name scalp-api -- -m server_api.main
pm2 start ./myvenv/bin/python --name scalp-feed -- -m services.market_price_feed
pm2 start ./myvenv/bin/python --name scalp-bot -- -m bot.main
```

С явным `cwd` (если запускаешь не из корня проекта):

```bash
pm2 start ./myvenv/bin/python --name scalp-api --cwd /root/multiuser_bot/Scalp_bot -- -m server_api.main
pm2 start ./myvenv/bin/python --name scalp-feed --cwd /root/multiuser_bot/Scalp_bot -- -m services.market_price_feed
pm2 start ./myvenv/bin/python --name scalp-bot --cwd /root/multiuser_bot/Scalp_bot -- -m bot.main
```

Перед повторным стартом (если уже пробовали с ошибкой):

```bash
pm2 delete scalp-api scalp-feed scalp-bot 2>/dev/null
```

**Управление**

```bash
pm2 status
pm2 logs scalp-api          # или scalp-feed, scalp-bot
pm2 restart scalp-api
pm2 stop scalp-api scalp-feed scalp-bot
pm2 delete scalp-api scalp-feed scalp-bot
pm2 save                    # сохранить список процессов
pm2 startup                 # автозапуск после перезагрузки ОС (один раз, выполни команду из вывода)
```

Проверка API: `curl http://127.0.0.1:8050/health`

> Celery через PM2 тоже можно, но ниже — вариант со **screen** (удобнее смотреть live-логи воркеров).

---

### Screen — Celery (router + engine workers)

Celery лучше держать в отдельных screen-сессиях рядом с PM2-процессами.

```bash
cd /path/to/Scalp_bot
source myvenv/bin/activate
```

**Создать сессии в фоне** (`TRADE_ENGINE_COUNT=2` — два engine, как в примере выше)

```bash
# Router (очереди default, trade_user)
screen -dmS scalp-router bash -lc '
  cd /path/to/Scalp_bot && source myvenv/bin/activate &&
  celery -A celery_app.celery_config worker \
    -Q default,trade_user --concurrency=4 -l info
'

# Celery Beat — проверка подписок (один экземпляр)
screen -dmS scalp-beat bash -lc '
  cd /path/to/Scalp_bot && source myvenv/bin/activate &&
  celery -A celery_app.celery_config beat -l info
'

# Engine 0
screen -dmS scalp-engine0 bash -lc '
  cd /path/to/Scalp_bot && source myvenv/bin/activate &&
  CELERY_ENGINE_ID=0 celery -A celery_app.celery_config worker \
    -Q trade_engine_0 -n engine0@%h --concurrency=1 -l info
'

# Engine 1
screen -dmS scalp-engine1 bash -lc '
  cd /path/to/Scalp_bot && source myvenv/bin/activate &&
  CELERY_ENGINE_ID=1 celery -A celery_app.celery_config worker \
    -Q trade_engine_1 -n engine1@%h --concurrency=1 -l info
'
```

**Подключиться к логам**

```bash
screen -ls
screen -r scalp-router    # выход: Ctrl+A, затем D
screen -r scalp-beat
screen -r scalp-engine0
screen -r scalp-engine1
```

**Остановить**

```bash
screen -S scalp-router -X quit
screen -S scalp-beat -X quit
screen -S scalp-engine0 -X quit
screen -S scalp-engine1 -X quit
```

**Рекомендуемый порядок старта (production)**

1. Redis + MongoDB  
2. `pm2 start` — **scalp-feed**  
3. **screen** — engine workers (`trade_engine_0` …)  
4. **screen** — **scalp-router**  
5. **screen** — **scalp-beat** (проверка подписок)  
6. `pm2 start` — **scalp-api**  
7. `pm2 start` — **scalp-bot** (если нужен Telegram)  
8. **screen** — **cloudflare** (туннель для TradingView, см. [шпаргалку](#деплой-на-сервер--шпаргалка-запуска))

После смены `.env` (например `USE_DEMO` или `SERVER_URL`): `pm2 restart scalp-api` (и `scalp-bot` при необходимости); перезапусти screen-сессии Celery и cloudflared при смене туннеля.

---

## Запуск торговли (multi)

Сигнал на символ. Тело запроса — тикер, опционально с маркером типа алерта через пробел
(регистронезависимо, парсит `server_api/utils.py::parse_short_signal_body`):

- `BTCUSDT` или `BTCUSDT SHORT SIGNAL` — обычная сделка (текущая логика: БУ+трейлинг по
  `TRIGGER_PERCENTAGE`, стоп по `STOP_LOSS_PERCENTAGE`, усредняющие лимитники по `COUNT_LIMIT_ORDERS`).
- `BTCUSDT Short1` — **режим повышенного риска**: БУ+трейлинг сразу по `RISK_MODE_TRIGGER_PERCENTAGE`
  (по умолчанию 1%), стоп по `RISK_MODE_STOP_LOSS_PERCENTAGE` (по умолчанию 10%), **без усредняющих
  лимитных ордеров**. Пользователь получает в сообщении о запуске строку "⚠️ Сделка с повышенным
  риском". Любой нераспознанный маркер трактуется как обычная сделка (безопасный дефолт).

**Локально (на сервере):**

```bash
curl -X POST http://127.0.0.1:8050/short_3_limit -d "BTCUSDT"
curl -X POST http://127.0.0.1:8050/short_3_limit -d "BTCUSDT Short1"
```

**Через Cloudflare (как TradingView):**

```bash
curl -X POST "https://ваш-url.trycloudflare.com/short_3_limit" -d "BTCUSDT"
```

В ответе: `queued` — сколько задач поставлено в Celery, `risk_mode` — распознан ли маркер `Short1`.

Цепочка:

```
/short_3_limit → short_3_limit (trade_user) → assign_trade → engine_execute_trade (trade_engine_N)
→ AsyncTradeEngine → цена из Redis (или local WS при feed down)
```

`risk_mode` прокидывается по всей этой цепочке как отдельный kwarg (`TradeState.risk_mode`) —
только для `/short_3_limit` (мультиюзер); `nomulti`/`hedge`/`custom_algo`/`demo_showcase` его не
используют и не затронуты.

## Подготовка пользователей в Mongo

Пользователь должен иметь:

- `subscription_data.subscription: true`
- `bybit_data.api_key`, `bybit_data.api_secret`
- `bybit_data.sum_for_trades` > 0
- `bybit_data.stop_trading` не `true`
- `bybit_data.max_concurrent_trades` — макс. одновременных сделок (по умолчанию `1`)

Опционально в `bybit_data` хранится `api_key_expired_at` (синхронизируется при входе в профиль) — для напоминаний об истечении ключа.

**Миграция** (если обновляешь существующую БД):

```bash
python -m scripts.migrate_max_concurrent_trades
```

Иначе он будет пропущен при `/short_3_limit`.

## Жизненный цикл подписки (Celery Beat)

Помимо ручного подтверждения админом, срок подписки контролируется автоматически.

### Что делает сервис

Каждые `SUBSCRIPTION_LIFECYCLE_CHECK_HOURS` часов (по умолчанию **12**) задача `check_subscription_lifecycle`:

1. Находит пользователей с `subscription=true` и заполненной `end_subscription_date`.
2. **За 3 дня** до окончания — отправляет напоминание в Telegram.
3. **За 1 день** — второе напоминание.
4. **После истечения** — ставит `subscription=false`, сбрасывает `wait_sub_confirmation`, уведомляет об отключении.

Повторные напоминания для одной и той же даты окончания не отправляются (поля `notify_3d_for_end`, `notify_1d_for_end`, `notify_expired_for_end` в Mongo).

### Запуск

```bash
# Beat (один процесс на сервер)
celery -A celery_app.celery_config beat -l info

# Router должен слушать default — там выполняется задача
celery -A celery_app.celery_config worker -Q default,trade_user --concurrency=4 -l info
```

`.env`:

```env
SUBSCRIPTION_LIFECYCLE_CHECK_HOURS=12
```

Ручная проверка:

```bash
celery -A celery_app.celery_config call check_subscription_lifecycle
```

Полное описание: [README.md](README.md) (раздел «Жизненный цикл подписки»).

## Жизненный цикл API-ключа (Celery Beat)

Параллельно с подписками Beat запускает `check_api_key_lifecycle` (тот же интервал `SUBSCRIPTION_LIFECYCLE_CHECK_HOURS`).

### Что делает сервис

1. Находит пользователей с заполненными `api_key` / `api_secret` и `bybit_data.api_key_expired_at`.
2. **За 3 дня** до истечения — напоминание создать новый ключ.
3. **За 1 день** — второе напоминание.
4. **В день истечения** — финальное уведомление.

Дата истечения обновляется при входе в **личный кабинет** / **настройки** и при сохранении key/secret (запрос `get_api_key_information` к Bybit). Если дата не изменилась — запись в Mongo не трогается.

Повторные напоминания для одной даты не отправляются (`notify_api_key_3d`, `notify_api_key_1d`, `notify_api_key_expired`).

**Ограничение:** для ключей с привязкой к IP Bybit не отдаёт срок — профиль и напоминания для таких ключей не работают.

Тест с ключами из `.env`:

```bash
python -m bybit_logic.ready_func.ex_api_key_info
```

Ручная проверка Celery:

```bash
celery -A celery_app.celery_config call check_api_key_lifecycle
```

Подробности: [README.md](README.md) (раздел «Жизненный цикл API-ключа Bybit»).

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
ADMIN_IDS=123456789,987654321
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
| Закрытие позиции, ошибка плеча | `NOMULTI_TG_ID` или первый ID из `ADMIN_IDS` |
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
| Celery Beat (подписки) | да | опционально (multi) |
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
| Напоминания о подписке не приходят | Запущен ли **Celery Beat**; router слушает `default`; у пользователя есть `end_subscription_date` |
| Rate limit Bybit | Увеличить `TRADE_SUBMIT_STAGGER_SEC` |

---

# Полезные ссылки

- [docs/phase2_scaling.md](docs/phase2_scaling.md) — архитектура Phase 2
- [docs/multiuser_demo_testing.md](docs/multiuser_demo_testing.md) — demo-тест 2 пользователей
- [tests/load/README.md](tests/load/README.md) — бенчмарки
- [README.md](README.md) — обзор async-движка
