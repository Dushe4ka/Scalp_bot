# Активация виртуального окружения

* python -m venv myvenv
* source myvenv/bin/activate

# Запуск сервера Scalp_api

* python -m server_api.main

# Запуск Celery Worker

* celery -A celery_app.celery_config worker --loglevel=info

# Запуск Telegram бота (мультиюзер)

* python -m bot.main

# Запуск Telegram бота (немультюзер)

* `python -m bot_nomultiuser.main` (из корня репозитория; в `.env` — `TELEGRAM_BOT_TOKEN`, `SERVER_URL`)

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

- `POST /hedge_long_short_bu_ts` — hedge long+short; тело: сырой текст символа (`BTCUSDT`); задача: `celery_app/tasks/hedge_long_short_bu_ts.py`
- `POST /nomulti_short_bu_ts_limit` — немультюзерный `short_bu_ts_limit`; тело: сырой текст символа; задача: `celery_app/tasks/short_bu_ts_limit_nomulti.py`

Немультюзерный Telegram-бот (`bot_nomultiuser`) вызывает эти эндпоинты из меню «Алгоритмы».

Примечание: для работы алгоритмов должны быть запущены API, Celery worker и общая MongoDB для подписчиков (уведомления идут через `send_notification_task`).