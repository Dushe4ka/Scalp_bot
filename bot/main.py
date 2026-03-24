import asyncio
from bot.utils.misc import bot, dp
from bot.handlers import start, subscription, profile, admin
from logger_config import setup_logger
from bot.middlewares.user_lang import UserLangMiddleware
from bot.middlewares.admin_only import AdminOnlyMiddleware

logger = setup_logger(__name__)

async def main():
    """Запуск бота"""
    # Регистрируем middleware
    dp.message.middleware(UserLangMiddleware())
    dp.callback_query.middleware(UserLangMiddleware())

    # Регистрируем роутеры
    dp.include_router(start.router)
    dp.include_router(subscription.router)
    dp.include_router(profile.router)

    # Админ-роутер + middleware только для админ-роутера
    admin.router.message.middleware(AdminOnlyMiddleware())
    admin.router.callback_query.middleware(AdminOnlyMiddleware())
    dp.include_router(admin.router)
    
    logger.info("Бот запущен")
    
    # Запускаем polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

