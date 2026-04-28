from fastapi import FastAPI
from server_api.routes import health, monitoring, trading, account
from logger_config import setup_logger
import uvicorn
from server_api.utils import get_ngrok_url
from celery_app.tasks.notifications import send_notification_task


logger = setup_logger(__name__)

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
        ngrok_url = get_ngrok_url(8000)
        logger.info(f"NGROK URL: {ngrok_url}")

        notification_text = (
            f"✅ Сервер запущен!\n\nNGROK URL: {ngrok_url.public_url}\n\n"
            f"Доступные эндпоинты:\n"
            f"{ngrok_url.public_url}/health\n"
            f"{ngrok_url.public_url}/monitoring\n"
            f"{ngrok_url.public_url}/short_3_limit\n"
            f"{ngrok_url.public_url}/hedge_long_short_bu_ts"
        )
        send_notification_task.delay(notification_text)
        logger.info(f"✅ Уведомление отправлено подписчикам о запуске сервера")

    except Exception as e:
        logger.error(f"Ошибка при получении ngrok URL: {e}")

    uvicorn.run(
        "server_api.main:app",
        host="127.0.0.1",
        port=8050,
        reload=True
    )
    