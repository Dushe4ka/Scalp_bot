import asyncio
from bot_nomultiuser.utils.misc import bot, dp
from bot_nomultiuser.handlers import start, subscription, server, trading, navigation, account
from logger_config import setup_logger

logger = setup_logger(__name__)

async def main():
    """Запуск бота"""
    # Регистрируем роутеры
    dp.include_router(start.router)
    dp.include_router(subscription.router)
    dp.include_router(server.router)
    dp.include_router(trading.router)
    dp.include_router(navigation.router)
    dp.include_router(account.router)

    logger.info("Бот запущен")
    
    # Запускаем polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

