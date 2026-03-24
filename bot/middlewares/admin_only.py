from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from config import ADMIN_IDS


class AdminOnlyMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = None
        if hasattr(event, "from_user") and event.from_user:
            user_id = event.from_user.id

        if user_id is None:
            return await handler(event, data)

        if user_id not in ADMIN_IDS:
            # Универсально отвечаем и для message, и для callback
            if isinstance(event, Message):
                await event.answer("Доступ запрещён")
            elif isinstance(event, CallbackQuery):
                await event.answer("Доступ запрещён", show_alert=True)
            return

        return await handler(event, data)