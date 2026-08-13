import os

from fastapi import FastAPI
from server_api.routes import health, monitoring, trading, account
from logger_config import setup_logger
import uvicorn
from celery_app.tasks.notifications import send_notification_task
from config import SERVER_URL


logger = setup_logger(__name__)

# reload=True запускает StatReload, который поллит mtime каждого файла в рабочей
# директории (включая myvenv/ — тысячи файлов) несколько раз в секунду — на проде
# это давало ~44% постоянной нагрузки CPU без единого реального запроса. Нужен
# только для локальной разработки, поэтому по умолчанию выключен.
UVICORN_RELOAD = os.getenv("UVICORN_RELOAD", "false").strip().lower() in ("true", "1", "yes")

# Создаем FastAPI приложение
app = FastAPI(
    title="Scalp Bot API",
    description="API для управления торговыми алгоритмами",
    version="1.0.0"
)

# Подключаем все роутеры
app.include_router(health.router)
app.include_router(monitoring.router)
app.include_router(trading.router)
app.include_router(account.router)

if __name__ == "__main__":
    try:
        base_url = SERVER_URL.rstrip("/")
        logger.info("PUBLIC URL: %s", base_url)

        notification_text = (
            f"✅ Сервер запущен!\n\nPUBLIC URL: {base_url}\n\n"
            f"Доступные эндпоинты:\n"
            f"🔻{base_url}/health\n\n"
            f"🔻{base_url}/monitoring\n\n"
            f"🔻{base_url}/short_3_limit\n\n"
            f"🔻{base_url}/hedge_long_short_bu_ts\n\n"
            f"— Nomulti (один аккаунт, сигнал POST телом = символ, кроме custom):\n"
            f"🔻{base_url}/nomulti_short_3_limit\n\n"
            f"🔻{base_url}/nomulti_custom_algo"
        )
        send_notification_task.delay(notification_text)
        logger.info(f"✅ Уведомление отправлено подписчикам о запуске сервера")

    except Exception as e:
        logger.error("Ошибка при формировании публичного URL: %s", e)

    uvicorn.run(
        "server_api.main:app",
        host="127.0.0.1",
        port=8050,
        reload=UVICORN_RELOAD
    )
    