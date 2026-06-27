from datetime import datetime
import asyncio
import aiohttp
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from bot.keyboards.inline_kb import (
    profile_menu_kb_without_subscription, 
    profile_menu_kb,
    profile_menu_wait_sub_confirmation_kb_without_subscription,
    profile_menu_wait_sub_confirmation_kb_with_subscription,
    profile_statistics_kb,
    profile_settings_kb,
    back_to_profile_settings_kb,
    profile_settings_sum_risk_kb,
    profile_balance_kb,
    profile_trading_kb,
    active_trades_page_kb,
    active_trade_details_kb,
    history_trades_page_kb,
    history_trade_details_kb,
)
from bot.callback_data.admin_lists import (
    HISTORY_TRADES_PAGE_SIZE,
    ActiveTradeItemCb,
    ActiveTradesPageCb,
    HistoryTradeItemCb,
    HistoryTradesPageCb,
)
from logger_config import setup_logger
from bot.utils.helpers import safe_edit_message, extract_user_api_credentials, get_recommended_trade_amount, notify_user_telegram
from bot.utils.api_key_expiry import refresh_user_api_key_expiry, build_api_key_expiry_line
from bot.utils.misc import _format_dt
from database.users_repository import db, UsersRepositoryError, ValidationError
from bot.languages._lang_func import get_config_lang
from bot.states.profile_states import ProfileStates
from typing import Any
from bybit_logic.bybit_func import account
from bybit_logic.bybit_func.session import create_session
from database.history_trades_repository import history_trades_db
from config import USE_DEMO
from bot.config import SERVER_URL

router = Router()
logger = setup_logger(__name__)

def _format_key_secret(key_secret: str) -> str:
    """Форматирует текст API ключа/секрета на первые 6 символов и последние 4 символа"""
    if len(key_secret) < 10:
        return key_secret
    else:
        return f"{key_secret[:6]}...{key_secret[-4:]}"


def _format_trade_history_row(idx: int, trade: dict[str, Any]) -> str:
    symbol = str(trade.get("symbol") or "—")
    side = str(trade.get("side") or "—")
    state = str(trade.get("state") or "closed").lower()
    pnl = float(trade.get("pnl_usdt") or 0)
    pnl_sign = "+" if pnl >= 0 else ""
    state_label = "🟢 active" if state == "active" else "⚪️ closed"
    return f"{idx}. {symbol} | {side} | {state_label} | PnL: {pnl_sign}{pnl:.2f} USDT"


def _format_history_dt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    text = str(value).strip()
    if not text:
        return "—"
    if "T" in text:
        text = text.replace("T", " ")
    return text[:16]


def _format_trade_details_text(text_config: dict[str, Any], trade: dict[str, Any]) -> str:
    symbol = str(trade.get("symbol") or "—")
    side = str(trade.get("side") or "—")
    state = str(trade.get("state") or "closed").lower()
    entry_price = float(trade.get("entry_price") or 0)
    exit_price = float(trade.get("exit_price") or 0)
    size = float(trade.get("size") or 0)
    pnl = float(trade.get("pnl_usdt") or 0)
    pnl_sign = "+" if pnl >= 0 else ""
    open_time = _format_history_dt(trade.get("open_time"))
    close_time = _format_history_dt(trade.get("close_time"))
    created_at = _format_history_dt(trade.get("created_at"))
    return (
        f"{text_config['profile_text']['profile_history_trade_details_title']}\n\n"
        f"📊 Символ: {symbol}\n"
        f"📈 Сторона: {side}\n"
        f"🏷️ Состояние: {state}\n"
        f"💰 Вход: {entry_price:.8g}\n"
        f"💸 Выход: {exit_price:.8g}\n"
        f"📦 Размер: {size:.8g}\n"
        f"💵 PnL: {pnl_sign}{pnl:.2f} USDT\n"
        f"🕒 Open: {open_time}\n"
        f"🕒 Close: {close_time}\n"
        f"🗂️ Добавлено: {created_at}"
    )


async def _render_history_trades_page(callback: CallbackQuery, lang: str, page: int) -> None:
    user_id = callback.from_user.id
    text_config = await get_config_lang(lang)
    total = await asyncio.to_thread(history_trades_db.count_user_trades, int(user_id))

    if total == 0:
        await safe_edit_message(
            callback,
            text_config["profile_text"]["profile_history_trades_empty"],
            reply_markup=(await profile_balance_kb(lang)).as_markup(),
        )
        return

    total_pages = max(1, (total + HISTORY_TRADES_PAGE_SIZE - 1) // HISTORY_TRADES_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    trades = await asyncio.to_thread(
        history_trades_db.list_user_trades_page,
        int(user_id),
        page=page,
        page_size=HISTORY_TRADES_PAGE_SIZE,
    )

    title = text_config["profile_text"]["profile_history_trades_title"].format(count=len(trades))
    page_info = text_config["profile_text"]["profile_history_trades_page"].format(
        page=page + 1,
        pages=total_pages,
        total=total,
    )
    text = f"{title}\n{page_info}"
    await safe_edit_message(
        callback,
        text,
        reply_markup=(await history_trades_page_kb(trades, page, total, lang)).as_markup(),
    )


async def _fetch_user_active_trades(user_id: int) -> list[dict[str, Any]]:
    async with aiohttp.ClientSession() as client:
        async with client.post(
            f"{SERVER_URL}/user_active_trades",
            json={"tg_id": int(user_id)},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(await resp.text())
            payload = await resp.json()
            return payload.get("active_trades", [])


async def _fetch_user_trade_info(user_id: int, symbol: str) -> dict[str, Any] | None:
    async with aiohttp.ClientSession() as client:
        async with client.post(
            f"{SERVER_URL}/user_result_position_info_by_symbol",
            json={"tg_id": int(user_id), "symbol": symbol},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(await resp.text())
            payload = await resp.json()
            return payload.get("result")


async def _stop_user_trade_by_symbol(user_id: int, symbol: str) -> dict[str, Any]:
    async with aiohttp.ClientSession() as client:
        async with client.post(
            f"{SERVER_URL}/user_stop_trading_by_symbol",
            json={"tg_id": int(user_id), "symbol": symbol},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(await resp.text())
            return await resp.json()


async def _stop_user_all_trades(user_id: int) -> dict[str, Any]:
    async with aiohttp.ClientSession() as client:
        async with client.post(
            f"{SERVER_URL}/user_stop_trading_all",
            json={"tg_id": int(user_id)},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(await resp.text())
            return await resp.json()


def _format_active_trade_details_text(text_config: dict[str, Any], trade: dict[str, Any] | None, symbol: str) -> str:
    if not trade:
        return text_config["profile_text"]["active_trade_not_found"].format(symbol=symbol)
    side = str(trade.get("side") or "—")
    size = float(trade.get("size") or 0)
    entry_price = float(trade.get("entry_price") or 0)
    pnl = float(trade.get("pnl_usdt") or 0)
    pnl_sign = "+" if pnl >= 0 else ""
    open_time = _format_history_dt(trade.get("open_time"))
    return (
        f"{text_config['profile_text']['active_trade_details_title']}\n\n"
        f"📊 Символ: {symbol}\n"
        f"📈 Сторона: {side}\n"
        f"📦 Размер: {size:.8g}\n"
        f"💰 Цена входа: {entry_price:.8g}\n"
        f"💵 PnL: {pnl_sign}{pnl:.2f} USDT\n"
        f"🕒 Open: {open_time}"
    )


async def _render_active_trades_page(callback: CallbackQuery, lang: str, page: int) -> None:
    text_config = await get_config_lang(lang)
    user_id = callback.from_user.id
    trades = await _fetch_user_active_trades(user_id)
    total = len(trades)
    if total == 0:
        await safe_edit_message(
            callback,
            text_config["profile_text"]["active_trades_empty"],
            reply_markup=(await profile_trading_kb(lang)).as_markup(),
        )
        return

    total_pages = max(1, (total + HISTORY_TRADES_PAGE_SIZE - 1) // HISTORY_TRADES_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * HISTORY_TRADES_PAGE_SIZE
    page_entries = trades[start:start + HISTORY_TRADES_PAGE_SIZE]
    text = text_config["profile_text"]["active_trades_page_title"].format(
        page=page + 1,
        pages=total_pages,
        total=total,
    )
    await safe_edit_message(
        callback,
        text,
        reply_markup=(await active_trades_page_kb(page_entries, page, total, lang)).as_markup(),
    )


async def _format_profile_text_by_template(user: dict[str, Any], text_config: dict[str, Any], type_settings: str) -> str:
    """Форматирует текст профиля по шаблону"""
    if type_settings == "profile_menu":
        template = text_config.get("profile_text", {}).get("profile_menu")

        payment_date = _format_dt(user["subscription_data"]["payment_date"])
        subscription_type = user["subscription_data"]["subscription_type"]
        sum_for_trades = user["bybit_data"]["sum_for_trades"]
        api_key = '✅' if user["bybit_data"]["api_key"] else '❌'
        api_key_expiry_line = build_api_key_expiry_line(
            user.get("bybit_data") or {},
            text_config["profile_text"]["profile_api_key_expiry"],
        )

        return template.format(
            payment_date=payment_date, 
            subscription_type=subscription_type, 
            sum_for_trades=sum_for_trades, 
            api_key=api_key,
            api_key_expiry_line=api_key_expiry_line,
        )

    elif type_settings == "profile_statistics":
        template = text_config.get("profile_text", {}).get("profile_statistics")

        total_trades = user["statistics"]["total_trades"]
        total_pnl = user["statistics"]["total_pnl"]
        positive_trades = user["statistics"]["positive_trades"]
        sum_positive_trades = user["statistics"]["sum_positive_trades"]
        negative_trades = user["statistics"]["negative_trades"]
        sum_negative_trades = user["statistics"]["sum_negative_trades"]

        return template.format(
            total_trades=total_trades, 
            total_pnl=total_pnl, 
            positive_trades=positive_trades, 
            sum_positive_trades=sum_positive_trades, 
            negative_trades=negative_trades, 
            sum_negative_trades=sum_negative_trades)

    elif type_settings == "profile_settings":
        template = text_config.get("profile_text", {}).get("profile_settings")

        api_key = _format_key_secret(user["bybit_data"]["api_key"])
        api_secret = _format_key_secret(user["bybit_data"]["api_secret"])
        sum_for_trades = user["bybit_data"]["sum_for_trades"]
        api_key_expiry_line = build_api_key_expiry_line(
            user.get("bybit_data") or {},
            text_config["profile_text"]["profile_api_key_expiry"],
        )

        return template.format(
            api_key=api_key, 
            api_secret=api_secret, 
            sum_for_trades=sum_for_trades,
            api_key_expiry_line=api_key_expiry_line,
        )

@router.callback_query(F.data == "profile_menu")
async def profile_menu(callback: CallbackQuery, lang: str):
    """Обработка нажатия на кнопку 'Мой профиль'"""

    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    is_subscriber = await db.is_subscriber(user_id)
    is_wait_sub_confirmation = await db.is_wait_sub_confirmation(user_id)
    
    text_config = await get_config_lang(lang)
    user = await db.get_user_by_username_or_id(user_id)
    if user and user.get("bybit_data", {}).get("api_key") and user.get("bybit_data", {}).get("api_secret"):
        user = await refresh_user_api_key_expiry(user)

    if is_subscriber and not is_wait_sub_confirmation: # sub true & wait false
        reply_markup = (await profile_menu_kb(user_id, lang)).as_markup()
        text = await _format_profile_text_by_template(user, text_config, "profile_menu")
    elif is_subscriber and is_wait_sub_confirmation: # sub true & wait true
        reply_markup = (await profile_menu_wait_sub_confirmation_kb_with_subscription(user_id, lang)).as_markup()
        text = await _format_profile_text_by_template(user, text_config, "profile_menu")
    elif not is_subscriber and is_wait_sub_confirmation: # sub false & wait true
        reply_markup = (await profile_menu_wait_sub_confirmation_kb_without_subscription(user_id, lang)).as_markup()
        text = text_config["profile_text"]["profile_menu_wait_sub_confirmation"]
    else: # sub false & wait false
        reply_markup = (await profile_menu_kb_without_subscription(user_id, lang)).as_markup()
        text = text_config["profile_text"]["profile_menu_without_subscription"]

    await safe_edit_message(callback, text, reply_markup=reply_markup)
    logger.info(f"Пользователь {user_id} ({username}) открыл меню 'Мой профиль'")

@router.callback_query(F.data == "statistics")
async def statistics(callback: CallbackQuery, lang: str):
    """Обработка нажатия на кнопку 'Статистика'"""

    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    
    text_config = await get_config_lang(lang)
    user = await db.get_user_by_username_or_id(user_id)

    text = await _format_profile_text_by_template(user, text_config, "profile_statistics")

    await safe_edit_message(
        callback, 
        text, 
        reply_markup=(await profile_statistics_kb(user_id, lang)).as_markup()
    )
    logger.info(f"Пользователь {user_id} ({username}) открыл меню 'Статистика'")

@router.callback_query(F.data == "settings_profile")
async def settings_profile(callback: CallbackQuery, lang: str):
    """Обработка нажатия на кнопку 'Настройки'"""

    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    
    text_config = await get_config_lang(lang)
    user = await db.get_user_by_username_or_id(user_id)
    if user and user.get("bybit_data", {}).get("api_key") and user.get("bybit_data", {}).get("api_secret"):
        user = await refresh_user_api_key_expiry(user)

    text = await _format_profile_text_by_template(user, text_config, "profile_settings")
    await safe_edit_message(
        callback, 
        text, 
        reply_markup=(await profile_settings_kb(user_id, lang)).as_markup()
    )
    logger.info(f"Пользователь {user_id} ({username}) открыл меню 'Настройки'")

@router.callback_query(F.data == "profile_settings_api_key_secret")
async def profile_settings_api_key_secret(callback: CallbackQuery, state: FSMContext, lang: str):
    """Пользователь начинает изменение API key/secret."""
    user_id = callback.from_user.id
    text_config = await get_config_lang(lang)

    text = text_config["profile_text"]["profile_settings_api_key"]

    await state.set_state(ProfileStates.edit_api_key)
    await callback.answer()
    await safe_edit_message(
        callback,
        text,
        reply_markup=(await back_to_profile_settings_kb(user_id, lang)).as_markup(),
    )


@router.message(ProfileStates.edit_api_key, F.text)
async def process_profile_edit_api_key(message: Message, state: FSMContext, lang: str):
    """Пользователь вводит API key, затем просим API secret."""
    text_config = await get_config_lang(lang)
    api_key = message.text.strip()

    text = text_config["profile_text"]["profile_settings_api_secret"]

    await state.update_data(new_api_key=api_key)
    await state.set_state(ProfileStates.edit_api_secret)
    await message.answer(
        text,
        reply_markup=(await back_to_profile_settings_kb(message.from_user.id, lang)).as_markup(),
    )


@router.message(ProfileStates.edit_api_secret, F.text)
async def process_profile_edit_api_secret(message: Message, state: FSMContext, lang: str):
    """Пользователь вводит API secret, сохраняем пару key/secret."""
    user_id = message.from_user.id
    username = message.from_user.username or ""
    text_config = await get_config_lang(lang)

    data = await state.get_data()
    api_key = data.get("new_api_key", "")
    api_secret = message.text.strip()

    try:
        await db.update_api_key(user_id, api_key)
        await db.update_api_secret(user_id, api_secret)
    except (ValidationError, UsersRepositoryError) as e:
        await message.answer(f"Не удалось обновить API key/secret: {e}")
        return

    user = await db.get_user_by_username_or_id(user_id)
    if user is None:
        await message.answer(text_config["admin_text"]["error_user_not_found"])
        await state.clear()
        return

    user = await refresh_user_api_key_expiry(user)

    await state.clear()
    await message.answer(
        await _format_profile_text_by_template(user, text_config, "profile_settings"),
        reply_markup=(await profile_settings_kb(user_id, lang)).as_markup(),
    )
    logger.info(f"Пользователь {user_id} ({username}) обновил API key/secret")


@router.callback_query(F.data == "profile_settings_sum_for_trades")
async def profile_settings_sum_for_trades(callback: CallbackQuery, state: FSMContext, lang: str):
    """Пользователь начинает изменение суммы сделки."""
    user_id = callback.from_user.id
    text_config = await get_config_lang(lang)
    user = await db.get_user_by_username_or_id(user_id)
    recommended_usdt: float | None = None
    if user is not None:
        recommended_usdt = await get_recommended_trade_amount(user)

    if recommended_usdt is not None:
        text = text_config["profile_text"]["profile_settings_sum_for_trades"].format(
            recommended_usdt=f"{recommended_usdt:.2f}"
        )
    else:
        text = text_config["profile_text"]["profile_settings_sum_for_trades_fallback"]

    await state.update_data(recommended_sum_for_trades=recommended_usdt)
    await state.set_state(ProfileStates.edit_sum_for_trades)
    await callback.answer()
    await safe_edit_message(
        callback,
        text,
        reply_markup=(await back_to_profile_settings_kb(user_id, lang)).as_markup(),
    )


@router.message(ProfileStates.edit_sum_for_trades, F.text)
async def process_profile_edit_sum_for_trades(message: Message, state: FSMContext, lang: str):
    """Пользователь вводит новую сумму сделки."""
    user_id = message.from_user.id
    username = message.from_user.username or ""
    text_config = await get_config_lang(lang)
    sum_for_trades = message.text.strip()
    state_data = await state.get_data()
    recommended_usdt = state_data.get("recommended_sum_for_trades")

    try:
        entered_sum = float(sum_for_trades)
        if entered_sum <= 0:
            await message.answer("Сумма сделки должна быть больше 0.")
            return
    except ValueError:
        await message.answer("Введите число (например: 25 или 25.5).")
        return

    if isinstance(recommended_usdt, (int, float)) and entered_sum > float(recommended_usdt):
        await state.update_data(pending_sum_for_trades=sum_for_trades)
        await state.set_state(ProfileStates.confirm_edit_sum_for_trades_risk)
        await message.answer(
            text_config["profile_text"]["profile_settings_sum_for_trades_risk_warning"].format(
                entered_sum=f"{entered_sum:.2f}",
                recommended_usdt=f"{float(recommended_usdt):.2f}",
            ),
            reply_markup=(await profile_settings_sum_risk_kb(lang)).as_markup(),
        )
        return

    try:
        await db.update_sum_for_trades(user_id, sum_for_trades)
    except (ValidationError, UsersRepositoryError) as e:
        await message.answer(f"Не удалось обновить сумму сделки: {e}")
        return

    user = await db.get_user_by_username_or_id(user_id)
    if user is None:
        await message.answer(text_config["admin_text"]["error_user_not_found"])
        await state.clear()
        return

    await state.clear()
    await message.answer(
        await _format_profile_text_by_template(user, text_config, "profile_settings"),
        reply_markup=(await profile_settings_kb(user_id, lang)).as_markup(),
    )
    logger.info(f"Пользователь {user_id} ({username}) обновил сумму сделки")


@router.callback_query(F.data == "profile_settings_sum_risk_confirm")
async def profile_settings_sum_risk_confirm(callback: CallbackQuery, state: FSMContext, lang: str):
    """Подтверждение рискованной суммы сделки."""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    text_config = await get_config_lang(lang)
    state_data = await state.get_data()
    sum_for_trades = str(state_data.get("pending_sum_for_trades") or "").strip()

    if not sum_for_trades:
        await callback.answer()
        await safe_edit_message(
            callback,
            text_config["profile_text"]["profile_settings_sum_for_trades_fallback"],
            reply_markup=(await back_to_profile_settings_kb(user_id, lang)).as_markup(),
        )
        await state.set_state(ProfileStates.edit_sum_for_trades)
        return

    try:
        await db.update_sum_for_trades(user_id, sum_for_trades)
    except (ValidationError, UsersRepositoryError) as e:
        await callback.answer()
        await safe_edit_message(callback, f"Не удалось обновить сумму сделки: {e}")
        return

    user = await db.get_user_by_username_or_id(user_id)
    if user is None:
        await callback.answer()
        await safe_edit_message(callback, text_config["admin_text"]["error_user_not_found"])
        await state.clear()
        return

    await callback.answer()
    await state.clear()
    await safe_edit_message(
        callback,
        await _format_profile_text_by_template(user, text_config, "profile_settings"),
        reply_markup=(await profile_settings_kb(user_id, lang)).as_markup(),
    )
    logger.info(f"Пользователь {user_id} ({username}) подтвердил рискованную сумму сделки")


@router.callback_query(F.data == "profile_settings_sum_risk_cancel")
async def profile_settings_sum_risk_cancel(callback: CallbackQuery, state: FSMContext, lang: str):
    """Отмена рискованной суммы и повторный ввод."""
    user_id = callback.from_user.id
    text_config = await get_config_lang(lang)
    state_data = await state.get_data()
    recommended_usdt = state_data.get("recommended_sum_for_trades")

    if isinstance(recommended_usdt, (int, float)):
        text = text_config["profile_text"]["profile_settings_sum_for_trades"].format(
            recommended_usdt=f"{float(recommended_usdt):.2f}"
        )
    else:
        text = text_config["profile_text"]["profile_settings_sum_for_trades_fallback"]

    await callback.answer()
    await state.set_state(ProfileStates.edit_sum_for_trades)
    await safe_edit_message(
        callback,
        text,
        reply_markup=(await back_to_profile_settings_kb(user_id, lang)).as_markup(),
    )


@router.callback_query(F.data == "trading_portfolio")
async def trading_portfolio(callback: CallbackQuery, lang: str):
    """Показать futures-баланс пользователя."""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    text_config = await get_config_lang(lang)
    user = await db.get_user_by_username_or_id(user_id)

    if user is None:
        await callback.answer()
        await safe_edit_message(callback, text_config["admin_text"]["error_user_not_found"])
        return

    api_key, api_secret = extract_user_api_credentials(user)
    if not api_key or not api_secret:
        await callback.answer()
        await safe_edit_message(
            callback,
            text_config["profile_text"]["profile_balance_api_missing"],
            reply_markup=(await profile_balance_kb(lang)).as_markup(),
        )
        return

    try:
        session = create_session(use_demo=USE_DEMO, api_key=api_key, api_secret=api_secret)
        balance = await asyncio.to_thread(account.get_futures_balance, session)
        balance_text = text_config["profile_text"]["profile_balance"].format(balance=f"{float(balance):.2f}")
    except Exception as e:
        logger.error("Ошибка получения баланса пользователя %s (%s): %s", user_id, username, e)
        balance_text = text_config["profile_text"]["profile_balance_error"]

    await callback.answer()
    await safe_edit_message(
        callback,
        balance_text,
        reply_markup=(await profile_balance_kb(lang)).as_markup(),
    )


@router.callback_query(F.data == "trading")
async def trading(callback: CallbackQuery, lang: str):
    """Меню торговли профиля."""
    text_config = await get_config_lang(lang)
    await callback.answer()
    await safe_edit_message(
        callback,
        text_config["profile_text"]["trading_menu"],
        reply_markup=(await profile_trading_kb(lang)).as_markup(),
    )


@router.callback_query(F.data == "history_trades")
async def history_trades(callback: CallbackQuery, lang: str):
    """Показать историю сделок пользователя."""
    try:
        await callback.answer()
        await _render_history_trades_page(callback, lang, page=0)
    except Exception as e:
        text_config = await get_config_lang(lang)
        logger.error("Ошибка получения истории сделок для %s: %s", callback.from_user.id, e, exc_info=True)
        await safe_edit_message(
            callback,
            text_config["profile_text"]["profile_history_trades_error"],
            reply_markup=(await profile_balance_kb(lang)).as_markup(),
        )


@router.callback_query(HistoryTradesPageCb.filter())
async def history_trades_page(callback: CallbackQuery, callback_data: HistoryTradesPageCb, lang: str):
    """Переключение страниц истории сделок."""
    await callback.answer()
    await _render_history_trades_page(callback, lang, page=int(callback_data.page))


@router.callback_query(HistoryTradeItemCb.filter())
async def history_trade_details(callback: CallbackQuery, callback_data: HistoryTradeItemCb, lang: str):
    """Детальная карточка сделки из истории."""
    user_id = callback.from_user.id
    text_config = await get_config_lang(lang)
    page = max(0, int(callback_data.page))
    idx = max(0, int(callback_data.idx))

    try:
        trades = await asyncio.to_thread(
            history_trades_db.list_user_trades_page,
            int(user_id),
            page=page,
            page_size=HISTORY_TRADES_PAGE_SIZE,
        )
    except Exception as e:
        logger.error("Ошибка чтения истории сделки user_id=%s: %s", user_id, e, exc_info=True)
        await callback.answer()
        await safe_edit_message(
            callback,
            text_config["profile_text"]["profile_history_trades_error"],
            reply_markup=(await profile_balance_kb(lang)).as_markup(),
        )
        return

    if idx >= len(trades):
        await callback.answer()
        await _render_history_trades_page(callback, lang, page=page)
        return

    trade = trades[idx]
    await callback.answer()
    await safe_edit_message(
        callback,
        _format_trade_details_text(text_config, trade),
        reply_markup=(await history_trade_details_kb(page, lang)).as_markup(),
    )


@router.callback_query(F.data == "active_trades")
async def active_trades(callback: CallbackQuery, lang: str):
    """Список активных сделок пользователя."""
    text_config = await get_config_lang(lang)
    try:
        await callback.answer()
        await _render_active_trades_page(callback, lang, page=0)
    except Exception as e:
        logger.error("Ошибка active_trades user_id=%s: %s", callback.from_user.id, e, exc_info=True)
        await safe_edit_message(
            callback,
            text_config["profile_text"]["active_trades_error"],
            reply_markup=(await profile_trading_kb(lang)).as_markup(),
        )


@router.callback_query(ActiveTradesPageCb.filter())
async def active_trades_page(callback: CallbackQuery, callback_data: ActiveTradesPageCb, lang: str):
    """Пагинация активных сделок."""
    text_config = await get_config_lang(lang)
    try:
        await callback.answer()
        await _render_active_trades_page(callback, lang, page=int(callback_data.page))
    except Exception as e:
        logger.error("Ошибка active_trades_page user_id=%s: %s", callback.from_user.id, e, exc_info=True)
        await safe_edit_message(
            callback,
            text_config["profile_text"]["active_trades_error"],
            reply_markup=(await profile_trading_kb(lang)).as_markup(),
        )


@router.callback_query(ActiveTradeItemCb.filter())
async def active_trade_details(callback: CallbackQuery, callback_data: ActiveTradeItemCb, lang: str):
    """Карточка активной сделки с live-инфо от сервера."""
    text_config = await get_config_lang(lang)
    user_id = callback.from_user.id
    page = max(0, int(callback_data.page))
    idx = max(0, int(callback_data.idx))
    try:
        trades = await _fetch_user_active_trades(user_id)
        start = page * HISTORY_TRADES_PAGE_SIZE
        entries = trades[start:start + HISTORY_TRADES_PAGE_SIZE]
        if idx >= len(entries):
            await callback.answer()
            await _render_active_trades_page(callback, lang, page=page)
            return
        symbol = str(entries[idx].get("symbol") or "").upper()
        trade_info = await _fetch_user_trade_info(user_id, symbol)
        await callback.answer()
        await safe_edit_message(
            callback,
            _format_active_trade_details_text(text_config, trade_info, symbol),
            reply_markup=(await active_trade_details_kb(symbol, page, lang)).as_markup(),
        )
    except Exception as e:
        logger.error("Ошибка active_trade_details user_id=%s: %s", user_id, e, exc_info=True)
        await safe_edit_message(
            callback,
            text_config["profile_text"]["active_trades_error"],
            reply_markup=(await profile_trading_kb(lang)).as_markup(),
        )


@router.callback_query(F.data.startswith("active_trade_stop:"))
async def active_trade_stop(callback: CallbackQuery, lang: str):
    """Остановка текущей активной сделки по символу."""
    text_config = await get_config_lang(lang)
    user_id = callback.from_user.id
    symbol = callback.data.split(":", 1)[1].strip().upper()
    try:
        result = await _stop_user_trade_by_symbol(user_id, symbol)
        await callback.answer()
        await safe_edit_message(
            callback,
            text_config["profile_text"]["active_trade_stop_success"].format(
                symbol=symbol,
                message=str(result.get("message") or ""),
            ),
            reply_markup=(await profile_trading_kb(lang)).as_markup(),
        )
    except Exception as e:
        logger.error("Ошибка active_trade_stop user_id=%s symbol=%s: %s", user_id, symbol, e, exc_info=True)
        await safe_edit_message(
            callback,
            text_config["profile_text"]["active_trade_stop_error"].format(symbol=symbol),
            reply_markup=(await profile_trading_kb(lang)).as_markup(),
        )


@router.callback_query(F.data == "profile_stop_all_trading")
async def profile_stop_all_trading(callback: CallbackQuery, lang: str):
    """Остановка всей торговли пользователя."""
    text_config = await get_config_lang(lang)
    user_id = callback.from_user.id
    try:
        result = await _stop_user_all_trades(user_id)
        await callback.answer()
        await safe_edit_message(
            callback,
            text_config["profile_text"]["stop_all_trading_success"].format(
                message=str(result.get("message") or ""),
            ),
            reply_markup=(await profile_trading_kb(lang)).as_markup(),
        )
    except Exception as e:
        logger.error("Ошибка profile_stop_all_trading user_id=%s: %s", user_id, e, exc_info=True)
        await safe_edit_message(
            callback,
            text_config["profile_text"]["stop_all_trading_error"],
            reply_markup=(await profile_trading_kb(lang)).as_markup(),
        )