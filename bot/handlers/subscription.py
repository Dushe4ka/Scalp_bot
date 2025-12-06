from aiogram import Router, F
from aiogram.types import CallbackQuery
from bot.keyboards.inline_kb import subscription_kb, main_menu_kb
from bot.utils.helpers import safe_edit_message
from database import add_subscriber, remove_subscriber, is_subscriber
from logger_config import setup_logger

router = Router()
logger = setup_logger(__name__)

@router.callback_query(F.data == "subscription")
async def subscription_menu(callback: CallbackQuery):
    """Меню подписки"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    
    text = "🔔 Подписка\n\n" \
           "Это подписка на оповещения по работе алгоритмов Scalp_bot.\n" \
           "Вы будете получать уведомления о важных событиях в работе торговых алгоритмов."
    
    await safe_edit_message(
        callback,
        text,
        reply_markup=subscription_kb(user_id).as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "subscribe")
async def subscribe(callback: CallbackQuery):
    """Подписка пользователя"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    
    add_subscriber(user_id, username)
    
    text = "✅ Вы успешно подписались на оповещения!\n\n" \
           "Вы будете получать уведомления о работе алгоритмов Scalp_bot."
    
    await safe_edit_message(
        callback,
        text,
        reply_markup=subscription_kb(user_id).as_markup()
    )
    await callback.answer("Вы подписались!")
    logger.info(f"Пользователь {user_id} ({username}) подписался")

@router.callback_query(F.data == "unsubscribe")
async def unsubscribe(callback: CallbackQuery):
    """Отписка пользователя"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    
    remove_subscriber(user_id)
    
    text = "❌ Вы отписались от оповещений.\n\n" \
           "Вы больше не будете получать уведомления о работе алгоритмов."
    
    await safe_edit_message(
        callback,
        text,
        reply_markup=subscription_kb(user_id).as_markup()
    )
    await callback.answer("Вы отписались!")
    logger.info(f"Пользователь {user_id} ({username}) отписался")

