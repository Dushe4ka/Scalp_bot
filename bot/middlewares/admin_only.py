from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from config import ADMIN_IDS


from bot.languages._lang_func import get_config_lang


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
            lang = data.get("lang") or "ru"
            text_config = await get_config_lang(lang)
            denied = text_config["admin_text"]["access_denied"]
            if isinstance(event, Message):
                await event.answer(denied)
            elif isinstance(event, CallbackQuery):
                await event.answer(denied, show_alert=True)
            return

        return await handler(event, data)