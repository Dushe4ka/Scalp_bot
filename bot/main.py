import asyncio
from bot.utils.misc import bot, dp
from bot.handlers import start, subscription, profile, admin
from logger_config import setup_logger
from bot.middlewares.user_lang import UserLangMiddleware
from bot.middlewares.admin_only import AdminOnlyMiddleware
from config import ADMIN_IDS
from database.app_settings_repository import app_settings_db
from database.users_repository import db
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat

logger = setup_logger(__name__)


async def setup_bot_commands() -> None:
    """Команды бота: /admin видна только админам (per-chat scope)."""
    default_commands = [
        BotCommand(command="start", description="Главное меню / Main menu"),
        BotCommand(command="main_menu", description="Главное меню / Main menu"),
        BotCommand(command="profile", description="Личный кабинет / Profile"),
        BotCommand(command="help", description="Справка / Help"),
    ]
    await bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())

    admin_commands = default_commands + [
        BotCommand(command="admin", description="Админ-панель / Admin panel"),
    ]
    for admin_id in sorted(ADMIN_IDS):
        try:
            await bot.set_my_commands(
                admin_commands,
                scope=BotCommandScopeChat(chat_id=int(admin_id)),
            )
        except Exception as e:
            logger.warning("Не удалось установить admin-команды для %s: %s", admin_id, e)


async def main():
    """Запуск бота"""
    await db.ensure_indexes()
    sync_stats = await app_settings_db.ensure_unlimited_trade_amount_admins(ADMIN_IDS)
    logger.info(
        "trade_amount_unlimited: admins synced added=%s total=%s",
        sync_stats.get("added"),
        sync_stats.get("total"),
    )

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

    await setup_bot_commands()
    logger.info("Бот запущен")
    
    # Запускаем polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

