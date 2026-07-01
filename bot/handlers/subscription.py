from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from bot.keyboards.inline_kb import (
    subscription_buy_kb,
    question_kb,
    input_payment_id_kb,
    input_payment_id_back_kb,
    confirm_payment_kb,
    confirm_payment_success_kb,
    prolong_subscription_kb,
    prolong_question_kb,
    prolong_input_payment_id_kb,
    prolong_input_payment_id_back_kb,
    prolong_confirm_payment_kb,

)
from logger_config import setup_logger
from bot.utils.helpers import safe_edit_message, send_info_payment_to_admin
from database.users_repository import db
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
    await state.update_data(payment_flow="buy")
    
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

    await state.update_data(payment_flow="buy")
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
    user_id = message.from_user.id
    payment_id = message.text.strip()

    text_config = await get_config_lang(lang)
    data = await state.get_data()
    payment_flow = str(data.get("payment_flow") or "buy").strip().lower()
    confirm_text = text_config["subscription_text"]["confirm_payment"].format(payment_id=payment_id)

    await state.update_data(payment_id=payment_id)
    await state.set_state(SubscriptionStates.waiting_confirm)

    await message.answer(
        confirm_text,
        reply_markup=(
            (await prolong_confirm_payment_kb(lang)).as_markup()
            if payment_flow == "prolong"
            else (await confirm_payment_kb(lang)).as_markup()
        )
    )

@router.callback_query(SubscriptionStates.waiting_confirm, F.data == "confirm_payment")
async def confirm_payment(callback: CallbackQuery, state: FSMContext, lang: str):
    """Обработка нажатия на кнопку 'Да'"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    data = await state.get_data()
    payment_id = str(data.get("payment_id") or "").strip()
    if not payment_id:
        await callback.answer("ID платежа не найден. Введите его заново.", show_alert=True)
        return

    await db.user_buy_subscription_30_days(user_id)

    sent = await send_info_payment_to_admin(payment_id, user_id, username)
    if not sent:
        logger.warning(
            "Не удалось отправить ID платежа админу после подтверждения: user_id=%s",
            user_id,
        )

    await state.clear()
    
    text_config = await get_config_lang(lang)
    text = text_config["subscription_text"]["confirm_payment_success"]
    
    await safe_edit_message(
        callback,
        text,
        reply_markup=(await confirm_payment_success_kb(lang)).as_markup()
    )
    logger.info(f"Пользователь {user_id} ({username}) подтвердил платеж и отправил ID платежа администратору")
    
@router.callback_query(F.data == "prolong_subscription")
async def prolong_subscription(callback: CallbackQuery, lang: str):
    """Обработка нажатия на кнопку 'Продлить подписку'"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    
    text_config = await get_config_lang(lang)
    text = text_config["subscription_text"]["prolong_subscription"]
    
    await safe_edit_message(
        callback,
        text,
        reply_markup=(await prolong_subscription_kb(user_id, lang)).as_markup()
    )
    logger.info(f"Пользователь {user_id} ({username}) открыл меню продления подписки")

@router.callback_query(F.data == "prolong_question")
async def prolong_question(callback: CallbackQuery, lang: str):
    """Обработка нажатия на кнопку 'Что дальше?'"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    
    text_config = await get_config_lang(lang)
    text = text_config["subscription_text"]["prolong_question"]
    
    await safe_edit_message(
        callback,
        text,
        reply_markup=(await prolong_question_kb(user_id, lang)).as_markup()
    )
    logger.info(f"Пользователь {user_id} ({username}) открыл меню 'Что дальше?' продления подписки")

@router.callback_query(F.data == "prolong_paid")
async def prolong_paid(callback: CallbackQuery, state: FSMContext, lang: str):
    """Обработка нажатия на кнопку 'Оплачено' продления подписки"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    await state.clear()
    await state.update_data(payment_flow="prolong")
    
    text_config = await get_config_lang(lang)
    text = text_config["subscription_text"]["prolong_paid"]
    
    await safe_edit_message(
        callback,
        text,
        reply_markup=(await prolong_input_payment_id_kb(user_id, lang)).as_markup()
    )
    logger.info(f"Пользователь {user_id} ({username}) открыл меню ввода ID платежа продления подписки")

@router.callback_query(F.data == "prolong_input_payment_id")
async def prolong_input_payment_id(callback: CallbackQuery, state: FSMContext, lang: str):
    """Обработка нажатия на кнопку 'Ввести ID платежа' продления подписки"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    await state.update_data(payment_flow="prolong")
    await state.set_state(SubscriptionStates.waiting_payment_id)
    
    text_config = await get_config_lang(lang)
    text = text_config["subscription_text"]["input_payment_id"]

    await safe_edit_message(
        callback,
        text,
        reply_markup=(await prolong_input_payment_id_back_kb(lang)).as_markup()
    )
    logger.info(f"Пользователь {user_id} ({username}) перешёл в ввод ID платежа продления подписки")

@router.callback_query(SubscriptionStates.waiting_confirm, F.data == "prolong_confirm_payment")
async def prolong_confirm_payment(callback: CallbackQuery, state: FSMContext, lang: str):
    """Обработка нажатия на кнопку 'Да' продления подписки"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    data = await state.get_data()
    payment_id = str(data.get("payment_id") or "").strip()
    if not payment_id:
        await callback.answer("ID платежа не найден. Введите его заново.", show_alert=True)
        return

    await db.user_buy_subscription_30_days(user_id)

    sent = await send_info_payment_to_admin(payment_id, user_id, username)
    if not sent:
        logger.warning(
            "Не удалось отправить ID платежа админу после подтверждения продления: user_id=%s",
            user_id,
        )

    await state.clear()
    
    text_config = await get_config_lang(lang)
    text = text_config["subscription_text"]["prolong_confirm_payment_success"]

    await safe_edit_message(
        callback,
        text,
        reply_markup=(await confirm_payment_success_kb(lang)).as_markup()
    )
    logger.info(f"Пользователь {user_id} ({username}) подтвердил платеж и отправил ID платежа администратору продления подписки")
