# bot/middlewares/user_lang.py
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from typing import Callable, Dict, Any, Awaitable

from database.users_repository import UsersRepository

# Один экземпляр на всё приложение
repo = UsersRepository()

class UserLangMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Достаём user_id из message или callback
        user_id = None
        username = ""
        if hasattr(event, "from_user") and event.from_user:
            user_id = event.from_user.id
            username = event.from_user.username or ""

        if user_id is None:
            return await handler(event, data)

        user = await repo.get_or_create_user(user_id, username)
        data["user"] = user
        data["lang"] = user.get("language", "ru")

        return await handler(event, data)