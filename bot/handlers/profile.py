from aiogram import Router, F
from aiogram.types import CallbackQuery
from bot.keyboards.inline_kb import (
    profile_menu_kb_without_subscription, 
    profile_menu_kb,
    profile_menu_wait_sub_confirmation_kb
)
from logger_config import setup_logger
from bot.utils.helpers import safe_edit_message
from users_repository import db
from bot.languages._lang_func import get_config_lang

router = Router()
logger = setup_logger(__name__)

@router.callback_query(F.data == "profile_menu")
async def profile_menu(callback: CallbackQuery, lang: str):
    """Обработка нажатия на кнопку 'Мой профиль'"""

    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    is_subscriber = await db.is_subscriber(user_id)
    text_config = await get_config_lang(lang)
    user = await db.get_user(user_id)

    if is_subscriber:
        reply_markup = (await profile_menu_kb(user_id, lang)).as_markup()
        text = text_config["profile_text"]["profile_menu"].format(
            payment_date=user["subscription_data"]["payment_date"],
            subscription_type=user["subscription_data"]["subscription_type"],
            sum_for_trades=user["bybit_data"]["sum_for_trades"],
            api_key='✅' if user["bybit_data"]["api_key"] else '❌'
        )
    elif user["subscription_data"]["wait_sub_confirmation"]:
        reply_markup = (await profile_menu_wait_sub_confirmation_kb(user_id, lang)).as_markup()
        text = text_config["profile_text"]["profile_menu_wait_sub_confirmation"]
    else:
        reply_markup = (await profile_menu_kb_without_subscription(user_id, lang)).as_markup()
        text = text_config["profile_text"]["profile_menu_without_subscription"]

    await safe_edit_message(callback, text, reply_markup=reply_markup)
    logger.info(f"Пользователь {user_id} ({username}) открыл меню 'Мой профиль'")
