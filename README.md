# Активация виртуального окружения

* python -m venv myvenv
* source myvenv/bin/activate

# Запуск сервера Scalp_api

* python -m server_api.main

# Запуск Celery Worker

* celery -A celery_app.celery_config worker --loglevel=info

# Запуск Telegram бота

* python -m bot.main