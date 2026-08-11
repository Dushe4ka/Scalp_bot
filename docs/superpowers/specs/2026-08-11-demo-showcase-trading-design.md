---
title: Demo-показ сделок для маркетинга (tg_id 490882969)
date: 2026-08-11
status: approved
---

# Demo-показ сделок для маркетинга

## Проблема

Отделу маркетинга нужны скриншоты «больших выигрышей» реального алгоритма для промо-материалов.
Пользователь `tg_id=490882969` (админ) должен получать в Telegram точно такие же уведомления о
сделках, как обычный подписчик мультиюзер-бота, но:

- торговля идёт на **demo-счёте Bybit** (там нет реальных денег и почти нет лимитов по сумме);
- сумма сделки — заметно больше обычной, чтобы PnL на скриншотах выглядел внушительно;
- сделки идут **синхронно с реальными сигналами** (тем же вызовом `/short_3_limit`, которым
  торгуют настоящие подписчики), а не по отдельной ручной команде;
- алгоритм — тот же самый, что используется в проде для мультиюзеров
  (`AsyncTradeEngine` / `TradeSession` из `short_bu_ts_limit_engine.py`), без дублирования логики.

## Ключевая находка (влияет на архитектуру)

`USE_DEMO` в `bybit_logic/api_algorithms/short_bu_ts_limit_engine.py` — module-level переменная
процесса (не параметр конкретной сделки). `BybitHttpAdapter.create_session` берёт её как глобал,
а `pybit`'s `HTTP(..., demo=use_demo)` реально переключает API-эндпоинт (demo vs mainnet).

При этом `/short_3_limit` (реальные подписчики) и `/nomulti_short_3_limit` в текущей Phase 2
архитектуре шардятся через общий пул `trade_engine_0/1` (`trade_orchestrator.assign_trade`), где
`AsyncTradeEngine` — синглтон на процесс, параллельно обслуживающий десятки сессий в одном event
loop.

**Вывод:** нельзя «подмешать» demo-сделку в этот общий пул — либо она не сможет использовать
demo-ключи (процесс живёт с `USE_DEMO=False` ради реальных денег подписчиков), либо переключение
`USE_DEMO` на лету — гонка состояний, способная случайно увести реальные сделки в demo-режим (или
наоборот). Трогать боевой `short_bu_ts_limit_engine.py` ради этой фичи — неприемлемый риск.

## Решение

Отдельный лёгкий Celery-воркер (свой процесс, своя очередь `demo_showcase`), с собственным
экземпляром `AsyncTradeEngine`, работающий **только в demo-режиме**. Импортирует классы
`TradeSession` / `AsyncTradeEngine` / `start_trading()` из `short_bu_ts_limit_engine.py`
**без единой правки** в этом файле — полное переиспользование торговой логики, полная изоляция от
реальных денег на уровне ОС-процесса.

Вся новая логика — в отдельной директории `demo_showcase/`, чтобы не нагромождать проект.

### Архитектура (поток данных)

```
Signal → POST /short_3_limit (server_api/routes/trading.py)
             │
             ├── как раньше: fan-out реальным подписчикам (без изменений)
             │
             └── demo_showcase.trigger.maybe_trigger_demo_showcase(symbol)
                       │  (не срабатывает, если DEMO_SHOWCASE_ENABLED=false)
                       ▼
                 Celery-задача на очереди "demo_showcase"
                 (отдельный воркер-процесс, USE_DEMO принудительно True)
                       │
                       ▼
                 short_bu_ts_limit_engine.start_trading(...)
                 ← та же TradeSession / AsyncTradeEngine, без изменений
                       │
                       ├── открытие / БУ / трейлинг / закрытие — как у обычного юзера
                       ├── Telegram-уведомления → tg_id 490882969 (обычный формат, с суммой)
                       └── аудит-запись в отдельную Mongo-коллекцию demo_showcase_trades
                           (НЕ в history_trades — не трогает профиль/статистику админа)
```

### Компоненты

Всё новое — только внутри `demo_showcase/`:

| Файл | Назначение |
|---|---|
| `demo_showcase/__init__.py` | пакет |
| `demo_showcase/config.py` | env: `DEMO_SHOWCASE_ENABLED`, `DEMO_SHOWCASE_TG_ID=490882969`, `DEMO_SHOWCASE_API_KEY`/`DEMO_SHOWCASE_API_SECRET` (отдельный demo-аккаунт, не пересекается с тестовым `DEMO_API_KEY`), `DEMO_SHOWCASE_USDT_AMOUNT`, `DEMO_SHOWCASE_NAME` |
| `demo_showcase/trigger.py` | `maybe_trigger_demo_showcase(symbol: str) -> None` — вызывается из `/short_3_limit`; проверяет `DEMO_SHOWCASE_ENABLED`, ставит Celery-задачу на очередь `demo_showcase` |
| `demo_showcase/tasks.py` | Celery-задача `demo_showcase_trade` (queue=`demo_showcase`); Redis-lock `trade:demo_showcase:{symbol}` (по образцу `nomulti_short_3_limit_task`), затем **явно** ставит `short_bu_ts_limit_engine.USE_DEMO = True` перед вызовом `start_trading(...)` — самодостаточная защита, не полагается только на env процесса |
| `demo_showcase/repository.py` | тонкий враппер над Mongo-коллекцией `demo_showcase_trades` (аудит: symbol, entry/exit price, pnl, timestamps) |

**Правки в существующих файлах — минимальные:**

- `server_api/routes/trading.py` — один импорт + один вызов `maybe_trigger_demo_showcase(symbol)` в `/short_3_limit`, после валидации символа, независимо от того, есть ли реальные подписчики (`queued`), чтобы точно отражать факт получения сигнала.
- `celery_app/celery_config.py` — добавить `Queue("demo_showcase")` в `task_queues` и `demo_showcase.tasks` в `imports` (тот же паттерн, что для всех остальных очередей — никакой новой абстракции).
- `.env` / `.env.example` — новые переменные из `demo_showcase/config.py`.

### Область действия

Хук вешается **только на `/short_3_limit`** — единственный реально активный вход для боевых
TradingView-сигналов в мультиюзер-боте (`/nomulti_short_3_limit` сейчас не используется —
`scalp-bot-nomulti` остановлен на сервере). Если nomulti-путь снова понадобится — хук туда
добавляется отдельной точечной правкой по той же схеме.

### Безопасность и изоляция от боевых денег

- Отдельный OS-процесс = отдельный Python-интерпретатор = свой собственный синглтон
  `AsyncTradeEngine`. Реальные `trade_engine_0/1` вообще не знают о существовании этого воркера.
- Даже если забудут выставить `USE_DEMO=true` в env этого процесса — таск сам форсирует
  `USE_DEMO=True` на модуле при старте, так что чужие деньги физически не могут пройти через этот
  путь.
- Ошибка в demo-сделке (невалидные demo-ключи, таймаут Bybit) — лог + `max_retries` у Celery-задачи,
  не влияет на ответ `/short_3_limit` реальным подписчикам (задача асинхронна, fire-and-forget).
- Дедупликация «не открывать вторую сделку по тому же символу, пока есть активная» — два уровня,
  оба переиспользуют существующие паттерны:
  - Redis-lock `trade:demo_showcase:{symbol}` в начале `demo_showcase_trade` — **тот же паттерн**,
    что уже используется в `nomulti_short_3_limit_task`
    (`celery_app/tasks/short_3_limit_nomulti.py`), защищает от гонки при двух почти одновременных
    вызовах `/short_3_limit` по одному символу (`if_position_open` сам по себе эту гонку не ловит —
    проверка происходит до старта ордера, а не атомарно с ним);
  - `TradeSession._bootstrap()` (`if_position_open` check) — уже встроенная защита на уровне
    движка, переиспользуется бесплатно как второй рубеж.

### Уведомления

Формат — стандартный, как у обычного подписчика (`_notify_user` из `TradeSession`, tg_id не входит
в `COMPACT_NOTIFY_TG_IDS`) — включая строку с суммой сделки и финальным PnL в USDT, что и нужно для
маркетинговых скриншотов. Никаких изменений в формат уведомлений вносить не требуется.

### Хранение истории

Demo-сделки **не пишутся** в `history_trades` — это сохранило бы реальную статистику/профиль
админа от искажения огромными «выигрышами». Вместо этого — отдельная Mongo-коллекция
`demo_showcase_trades`, чисто аудит-лог (не участвует в UI бота).

### Деплой

Новый процесс в screen/PM2 рядом с существующими `multi_scalp_engine_0/1`:

```
USE_DEMO=true celery -A celery_app.celery_config worker -Q demo_showcase --concurrency=1
```

(Детали процедуры запуска/скриптов — в плане реализации, не в этой спеке.)

### Тестирование

- Unit: `demo_showcase/trigger.py` — не ставит задачу при `DEMO_SHOWCASE_ENABLED=false`; ставит
  задачу с правильными kwargs при `true`.
- Unit: `demo_showcase/tasks.py` — мокнутый `start_trading`, проверить что `USE_DEMO` действительно
  форсируется в `True` перед вызовом.
- Manual/integration: ручной прогон `celery -A celery_app.celery_config call demo_showcase_trade
  --kwargs '{"symbol": "BTCUSDT"}'` на staging/сервере с валидными demo-ключами — проверить, что
  сделка реально открывается на demo-эндпоинте Bybit и уведомление приходит tg_id 490882969.

## Не в рамках этой фичи (сознательно исключено)

- Никакого UI/кнопок в боте для управления этой функцией — только env-флаг `DEMO_SHOWCASE_ENABLED`,
  переключаемый на сервере.
- Никакой sharding/orchestrator логики — воркер всегда один и тот же, `--concurrency=1`, не нужен
  Redis-балансировщик, рассчитанный на десятки параллельных подписчиков.
- Хук на `/nomulti_short_3_limit` — не добавляется, т.к. этот путь сейчас не используется в проде.
