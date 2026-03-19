from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from bot.keyboards.inline_kb import (
    subscription_buy_kb,
    question_kb,
    input_payment_id_kb,
    input_payment_id_back_kb,
    confirm_payment_kb,
    confirm_payment_success_kb
)
from logger_config import setup_logger
from bot.utils.helpers import safe_edit_message
from users_repository import db
from bot.languages._lang_func import get_config_lang
from bot.states.subscription_states import SubscriptionStates
from aiogram.fsm.context import FSMContext

router = Router()
logger = setup_logger(__name__)

@router.callback_query(F.data == "subscription_buy")
async def subscription_buy(callback: CallbackQuery, lang: str):
    """Обработка нажатия на кнопку "Приобрести подписку"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    
    text_config = await get_config_lang(lang)
    text = text_config["subscription_text"]["buy_info"]

    await safe_edit_message(
        callback,
        text,
        reply_markup=(await subscription_buy_kb(user_id, lang)).as_markup()
    )
    logger.info(f"Пользователь {user_id} ({username}) открыл меню приобретения подписки")

@router.callback_query(F.data == "question")
async def question(callback: CallbackQuery, lang: str):
    """Обработка нажатия на кнопку 'Что дальше?'"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    
    text_config = await get_config_lang(lang)
    text = text_config["subscription_text"]["question"]
    
    await safe_edit_message(
        callback,
        text,
        reply_markup=(await question_kb(user_id, lang)).as_markup()
    )
    logger.info(f"Пользователь {user_id} ({username}) открыл меню 'Что дальше?'")

@router.callback_query(F.data == "paid")
async def paid(callback: CallbackQuery, state: FSMContext, lang: str):
    """Обработка нажатия на кнопку 'Оплачено'"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    await state.clear()
    
    text_config = await get_config_lang(lang)
    text = text_config["subscription_text"]["paid"]
    
    await safe_edit_message(
        callback,
        text,
        reply_markup=(await input_payment_id_kb(user_id, lang)).as_markup()
    )
    logger.info(f"Пользователь {user_id} ({username}) открыл меню ввода ID платежа")

@router.callback_query(F.data == "input_payment_id")
async def input_payment_id(callback: CallbackQuery, state: FSMContext, lang: str):
    """Показать приглашение ввести ID и перевести в состояние ожидания сообщения"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    text_config = await get_config_lang(lang)
    text = text_config["subscription_text"]["input_payment_id"]  # например "Введите ID платежа в чат"

    await state.set_state(SubscriptionStates.waiting_payment_id)

    await safe_edit_message(
        callback,
        text,
        reply_markup=(await input_payment_id_back_kb(lang)).as_markup()  # только кнопка "Назад"
    )
    logger.info(f"Пользователь {user_id} ({username}) перешёл в ввод ID платежа")

@router.message(SubscriptionStates.waiting_payment_id, F.text)
async def process_payment_id_message(message: Message, state: FSMContext, lang: str):
    """Пользователь прислал ID платежа текстовым сообщением"""
    payment_id = message.text.strip()

    await state.update_data(payment_id=payment_id)
    await state.set_state(SubscriptionStates.waiting_confirm)

    text_config = await get_config_lang(lang)
    confirm_text = text_config["subscription_text"]["confirm_payment"].format(payment_id=payment_id)
    # например: "Все верно: {payment_id}"

    await message.answer(
        confirm_text,
        reply_markup=(await confirm_payment_kb(lang)).as_markup()  # кнопки "Да ✓" / "Нет ✗"
    )

@router.callback_query(F.data == "confirm_payment")
async def confirm_payment(callback: CallbackQuery, state: FSMContext, lang: str):
    """Обработка нажатия на кнопку 'Да'"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    await db.update_wait_sub_confirmation(user_id, True)
    await state.clear()
    
    text_config = await get_config_lang(lang)
    text = text_config["subscription_text"]["confirm_payment_success"]
    
    await safe_edit_message(
        callback,
        text,
        reply_markup=(await confirm_payment_success_kb(lang)).as_markup()
    )
    logger.info(f"Пользователь {user_id} ({username}) подтвердил платеж и отправил ID платежа администратору")
    