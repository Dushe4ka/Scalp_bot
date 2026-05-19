# Quickstart

Ниже два сценария запуска:
- мультиюзерная версия (`bot`)
- немультиюзерная версия (`bot_nomultiuser`)

Обе версии используют один и тот же API и Celery.

## 1) Подготовка окружения

```bash
python -m venv myvenv
source myvenv/bin/activate
```

Убедись, что заполнены переменные в `.env` (минимум):
- `TELEGRAM_BOT_TOKEN`
- `SERVER_URL` (по умолчанию `http://127.0.0.1:8050`)
- `MONGO_URI`, `MONGO_DB`
- `REDIS_URL` (через `celery_app/config.py`)
- Bybit-ключи (для алгоритмов, в зависимости от вашего режима)

## 2) Запуск общих сервисов (для обеих версий)

### API

```bash
python -m server_api.main
```

Сервер поднимается на `127.0.0.1:8050`.

### Celery worker

```bash
celery -A celery_app.celery_config worker --loglevel=info -Q default,trade_user
```

## 3) Мультиюзерная версия

### Telegram-бот

```bash
python -m bot.main
```

### Как запускается торговля

- Бот вызывает мультиюзерный эндпоинт:
  - `POST /short_3_limit`
- По каждому подходящему пользователю ставится отдельная Celery-задача.

## 4) Немультиюзерная версия

### Telegram-бот

```bash
python -m bot_nomultiuser.main
```

### Доступные алгоритмы из меню бота

- `Short 3 limit (nomulti)`:
  - `POST /nomulti_short_3_limit`
  - Celery task: `celery_app/tasks/short_3_limit_nomulti.py`
- `Hedge long + short`:
  - `POST /hedge_long_short_bu_ts`
  - Celery task: `celery_app/tasks/hedge_long_short_bu_ts.py`

## 5) Проверка, что все в связке

1. Убедись, что API отвечает:
   - `GET /health`
2. Убедись, что worker подключен к `trade_user` и `default`.
3. Запусти нужного бота (`bot` или `bot_nomultiuser`).
4. В боте подпишись на уведомления.
5. Запусти алгоритм из меню:
   - в логах API должен быть `status: started`
   - в логах Celery должен появиться запуск соответствующей задачи
6. После завершения алгоритма должно прийти сообщение подписчикам (через `send_notification_task`).

## 6) Полезно для отладки

- Если бот не запускает алгоритм: проверь `SERVER_URL` в `.env`.
- Если нет уведомлений: проверь `TELEGRAM_BOT_TOKEN`, Mongo (`subscribers`) и что Celery жив.
- Если задачи не выполняются: проверь Redis и что worker слушает `trade_user`.
