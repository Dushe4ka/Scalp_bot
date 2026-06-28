from datetime import datetime
from typing import Any
import aiohttp

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from logger_config import setup_logger
from bot.languages._lang_func import get_config_lang
from bot.keyboards.inline_kb import (
    admin_menu_kb,
    users_list_kb,
    wait_confirm_kb,
    search_wait_confirm_user_kb,
    positive_proccess_search_wait_confirm_user_kb,
    positive_proccess_search_wait_confirm_user_kb_with_subscription,
    subscribers_kb,
    positive_proccess_search_subscribers_kb,
    search_subscribers_kb,
    subscription_settings_kb,
    bybit_settings_kb,
    statistics_info_kb,
    back_to_bybit_settings_kb,
    back_to_subscription_settings_kb,
    wait_confirm_list_page_kb,
    subscribers_list_page_kb,
    statistics_project_kb,
    server_kb,
    back_to_server_kb,
)
from bot.callback_data.admin_lists import (
    ADMIN_LIST_PAGE_SIZE,
    WaitConfirmListPageCb,
    WaitConfirmUserCb,
    AdminOpenUserCb,
    SubscribersListPageCb,
    SubscribersUserCb,
)
from bot.utils.helpers import safe_edit_message, notify_user_telegram
from bot.utils.misc import _format_dt
from bot.states.admin_states import AdminStates
from database.users_repository import db, UsersRepositoryError, ValidationError
from database.app_settings_repository import app_settings_db, AppSettingsRepositoryError
from config import LOCAL_SERVER_URL


router = Router()
logger = setup_logger(__name__)


async def _notify_user_payment_status(
    bot,
    user: dict[str, Any],
    message_key: str,
) -> None:
    tg_id = int(user["tg_id"])
    user_lang = user.get("language") or "ru"
    text_config = await get_config_lang(user_lang)
    text = text_config.get("subscription_text", {}).get(message_key)
    if not text:
        return
    await notify_user_telegram(bot, tg_id, text)


async def _wait_confirm_kb_from_list(state: FSMContext) -> bool:
    return bool((await state.get_data()).get("wait_confirm_from_list"))


async def _subscribers_kb_from_list(state: FSMContext) -> bool:
    return bool((await state.get_data()).get("subscribers_from_list"))


async def _subscribers_trade_amount_limit_status(tg_id: int, text_config: dict[str, Any]) -> str:
    is_unlimited = await app_settings_db.is_unlimited_trade_amount(int(tg_id))
    key = "trade_amount_limit_unlimited" if is_unlimited else "trade_amount_limit_standard"
    return text_config["admin_text"][key]


async def _render_subscriber_card(
    target,
    user_info: dict[str, Any],
    state: FSMContext,
    lang: str,
    *,
    from_subscribers_list: bool,
    edit: bool = True,
) -> None:
    text_config = await get_config_lang(lang)
    tg_id = int(user_info["tg_id"])
    limit_status = await _subscribers_trade_amount_limit_status(tg_id, text_config)
    text = _format_admin_subscribers_text_by_template(
        _user_doc_for_template(user_info),
        text_config,
        "main",
        trade_amount_limit_status=limit_status,
    )
    kb = (
        await positive_proccess_search_subscribers_kb(
            lang,
            from_subscribers_list=from_subscribers_list,
            target_tg_id=tg_id,
        )
    ).as_markup()
    if edit:
        await safe_edit_message(target, text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


def _user_doc_for_template(doc: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in doc.items() if k != "_id"}

def _format_admin_user_text_by_template(user: dict[str, Any], text_config: dict[str, Any]) -> str:
    template = text_config.get("admin_text", {}).get("user_info")

    subscription_data = user.get("subscription_data") or {}
    subscription = subscription_data.get("subscription")
    subscription_status = "Активна" if subscription else "Не активна"

    return template.format(
        name=user.get("name", "—"),
        tg_id=user.get("tg_id", "—"),
        language=user.get("language", "—"),
        subscription_status=subscription_status,
        current_amount=subscription_data.get("current_amount", "—"),
        subscription_type=subscription_data.get("subscription_type") or "—",
        payment_date=_format_dt(subscription_data.get("payment_date")),
        end_subscription_date=_format_dt(subscription_data.get("end_subscription_date")),
    )

def _format_admin_subscribers_text_by_template(
    user: dict[str, Any],
    text_config: dict[str, Any],
    type_settings: str,
    *,
    trade_amount_limit_status: str | None = None,
) -> str:
    if type_settings == "main":
        template = text_config.get("admin_text", {}).get("subscribers_main_info")
        return template.format(
            name=user.get("name", "—"),
            tg_id=user.get("tg_id", "—"),
            language=user.get("language", "—"),
            trade_amount_limit_status=trade_amount_limit_status or "—",
        )
    elif type_settings == "subscription_settings":
        template = text_config.get("admin_text", {}).get("subscription_settings")
        
        subscription_data = user.get("subscription_data") or {}
        subscription = subscription_data.get("subscription")
        subscription_status = "Активна" if subscription else "Не активна"
        
        return template.format(
            subscription_status=subscription_status,
            current_amount=subscription_data.get("current_amount", "—"),
            total_amount=subscription_data.get("total_amount", "—"),
            subscription_type=subscription_data.get("subscription_type") or "—",
            payment_date=_format_dt(subscription_data.get("payment_date")),
            end_subscription_date=_format_dt(subscription_data.get("end_subscription_date")),
        )

    elif type_settings == "bybit_settings":
        template = text_config.get("admin_text", {}).get("bybit_settings")

        bybit_data = user.get("bybit_data") or {}
        api_key = "✅" if bybit_data.get("api_key") else "❌"
        api_secret = "✅" if bybit_data.get("api_secret") else "❌"
        stop_trading = "Да" if bybit_data.get("stop_trading") is True else "Нет"
        return template.format(
            api_key=api_key,
            api_secret=api_secret,
            sum_for_trades=bybit_data.get("sum_for_trades", "—"),
            # open_trades=bybit_data.get("open_trades", "—"),
            stop_trading=stop_trading,
        )

    elif type_settings == "statistics_info":
        template = text_config.get("admin_text", {}).get("statistics_info")
        
        statistics_data = user.get("statistics") or {}

        return template.format(
            total_trades=statistics_data.get("total_trades", "—"),
            total_pnl=statistics_data.get("total_pnl", "—"),
            positive_trades=statistics_data.get("positive_trades", "—"),
            sum_positive_trades=statistics_data.get("sum_positive_trades", "—"),
            negative_trades=statistics_data.get("negative_trades", "—"),
            sum_negative_trades=statistics_data.get("sum_negative_trades", "—"),
        )

async def _format_admin_statistics_project_text_by_template(text_config: dict[str, Any]) -> str:
    template = text_config.get("admin_text", {}).get("statistics_project")
    total_users = await db.get_count_all_users()
    total_subscribers = await db.get_count_subscribers()
    total_users_waiting_confirmation = await db.get_count_users_waiting_confirmation()
    return template.format(
        total_users=total_users,
        total_subscribers=total_subscribers,
        total_users_waiting_confirmation=total_users_waiting_confirmation,
    )

@router.message(Command("admin"))
async def admin_start(message: Message, lang: str):
    """Обработка команды /admin"""
    user_id = message.from_user.id
    username = message.from_user.username or ""

    text_config = await get_config_lang(lang)
    text = text_config["admin_text"]["admin_menu"]

    await message.answer(
        text,
        reply_markup=(await admin_menu_kb(user_id, lang)).as_markup()
    )
    logger.info(f"Пользователь {user_id} ({username}) открыл админ-панель")

@router.callback_query(F.data == "admin_menu")
async def admin_menu(callback: CallbackQuery, lang: str):
    """Обработка нажатия на кнопку "Админ-панель"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    text_config = await get_config_lang(lang)
    text = text_config["admin_text"]["admin_menu"]

    await safe_edit_message(
        callback,
        text,
        reply_markup=(await admin_menu_kb(user_id, lang)).as_markup()
    )
    logger.info(f"Пользователь {user_id} ({username}) открыл админ-панель")


@router.callback_query(F.data == "admin_stop_all_trading")
async def admin_stop_all_trading(callback: CallbackQuery, lang: str):
    """Остановить всю торговлю через server API."""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    text_config = await get_config_lang(lang)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{LOCAL_SERVER_URL}/stop_trading_all_subscribers",
                timeout=aiohttp.ClientTimeout(total=20),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    report = (
                        f"{data.get('message', 'Массовая остановка завершена')}\n\n"
                        f"👥 Проверено пользователей: {data.get('processed', 0)}\n"
                        f"✅ Успешно остановлено: {data.get('stopped', 0)}\n"
                        f"⏭️ Пропущено (нет API ключей): {data.get('skipped_no_keys', 0)}\n"
                        f"❌ Ошибок: {data.get('errors_count', 0)}"
                    )
                    text = text_config["admin_text"]["stop_all_trading_success"].format(
                        message=report,
                    )
                else:
                    error_text = await response.text()
                    text = text_config["admin_text"]["stop_all_trading_error"].format(
                        error=error_text,
                    )
    except Exception as e:
        text = text_config["admin_text"]["stop_all_trading_error"].format(error=str(e))
        logger.error("Ошибка admin_stop_all_trading: %s", e, exc_info=True)

    await callback.answer()
    await safe_edit_message(
        callback,
        text,
        reply_markup=(await admin_menu_kb(user_id, lang)).as_markup(),
    )
    logger.info("Админ %s (%s) выполнил остановку всей торговли", user_id, username)

@router.callback_query(F.data == "users_list")
async def users_list(callback: CallbackQuery, lang: str):
    """Обработка нажатия на кнопку "Список пользователей"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    text_config = await get_config_lang(lang)
    text = text_config["admin_text"]["users_list"]

    await safe_edit_message(
        callback,
        text,
        reply_markup=(await users_list_kb(user_id, lang)).as_markup())
    logger.info(f"Пользователь {user_id} ({username}) открыл список пользователей")

# -------------------------------------------------------------
# Статистика проекта
# -------------------------------------------------------------

@router.callback_query(F.data == "statistics_project")
async def statistics_project(callback: CallbackQuery, lang: str):
    """Обработка нажатия на кнопку "Статистика проекта"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    text_config = await get_config_lang(lang)
    text = await _format_admin_statistics_project_text_by_template(text_config)
    await safe_edit_message(
        callback,
        text,
        reply_markup=(await statistics_project_kb(user_id, lang)).as_markup())
    logger.info(f"Пользователь {user_id} ({username}) открыл статистику проекта")

# -------------------------------------------------------------
# Ожидающие подтверждения
# -------------------------------------------------------------

@router.callback_query(F.data == "wait_confirm")
async def wait_confirm(callback: CallbackQuery, state: FSMContext, lang: str):
    """Обработка нажатия на кнопку "Ожидающие подтверждения"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    await state.clear()

    text_config = await get_config_lang(lang)
    text = text_config["admin_text"]["wait_confirm"]

    await safe_edit_message(
        callback,
        text,
        reply_markup=(await wait_confirm_kb(user_id, lang)).as_markup())
    logger.info(f"Пользователь {user_id} ({username}) открыл список ожидающих подтверждения")


async def _render_wait_confirm_list(callback: CallbackQuery, state: FSMContext, lang: str, page: int) -> None:
    await state.update_data(wait_confirm_from_list=False)
    text_config = await get_config_lang(lang)
    try:
        total = await db.count_users_waiting_confirmation()
    except UsersRepositoryError as e:
        await callback.answer(str(e), show_alert=True)
        return
    if total == 0:
        text = text_config["admin_text"]["wait_confirm_list_empty"]
        entries: list[dict[str, Any]] = []
        page = 0
    else:
        pages = max(1, (total + ADMIN_LIST_PAGE_SIZE - 1) // ADMIN_LIST_PAGE_SIZE)
        page = max(0, min(page, pages - 1))
        skip = page * ADMIN_LIST_PAGE_SIZE
        try:
            entries = await db.list_users_waiting_confirmation(skip, ADMIN_LIST_PAGE_SIZE)
        except UsersRepositoryError as e:
            await callback.answer(str(e), show_alert=True)
            return
        text = text_config["admin_text"]["wait_confirm_list_title"].format(
            page=page + 1,
            pages=pages,
            total=total,
        )
    await callback.answer()
    await safe_edit_message(
        callback,
        text,
        reply_markup=(await wait_confirm_list_page_kb(entries, page, total, lang)).as_markup(),
    )


@router.callback_query(F.data == "wait_confirm_list")
async def wait_confirm_list_open(callback: CallbackQuery, state: FSMContext, lang: str):
    """Список ожидающих подтверждения с пагинацией."""
    await _render_wait_confirm_list(callback, state, lang, 0)


@router.callback_query(WaitConfirmListPageCb.filter())
async def wait_confirm_list_page(callback: CallbackQuery, callback_data: WaitConfirmListPageCb, state: FSMContext, lang: str):
    await _render_wait_confirm_list(callback, state, lang, callback_data.page)


async def _render_admin_user_card(
    callback: CallbackQuery,
    user_info: dict[str, Any],
    state: FSMContext,
    lang: str,
) -> None:
    text_config = await get_config_lang(lang)
    subscription_data = user_info.get("subscription_data") or {}
    wait_confirm = subscription_data.get("wait_sub_confirmation")
    is_subscriber = subscription_data.get("subscription")
    tg_id = user_info.get("tg_id")

    await state.update_data(tg_id=tg_id, wait_confirm_from_list=False)
    text = _format_admin_user_text_by_template(_user_doc_for_template(user_info), text_config)

    if wait_confirm and not is_subscriber:
        kb = await positive_proccess_search_wait_confirm_user_kb(
            lang,
            from_wait_list=await _wait_confirm_kb_from_list(state),
        )
    elif wait_confirm and is_subscriber:
        kb = await positive_proccess_search_wait_confirm_user_kb_with_subscription(
            lang,
            from_wait_list=await _wait_confirm_kb_from_list(state),
        )
    else:
        text = f"{text}\n\nℹ️ Пользователь ещё не подтвердил оплату в боте (не нажал «Да ✓»)."
        kb = await search_wait_confirm_user_kb(callback.from_user.id, lang)

    await safe_edit_message(callback, text, reply_markup=kb.as_markup())


@router.callback_query(AdminOpenUserCb.filter())
async def admin_open_user_from_payment(
    callback: CallbackQuery,
    callback_data: AdminOpenUserCb,
    state: FSMContext,
    lang: str,
):
    """Открыть карточку пользователя из уведомления об оплате."""
    text_config = await get_config_lang(lang)
    user_info = await db.get_user(int(callback_data.tg_id))
    if user_info is None:
        await callback.answer(text_config["admin_text"]["error_user_not_found"], show_alert=True)
        return
    await callback.answer()
    await _render_admin_user_card(callback, user_info, state, lang)


@router.callback_query(WaitConfirmUserCb.filter())
async def wait_confirm_list_pick_user(
    callback: CallbackQuery,
    callback_data: WaitConfirmUserCb,
    state: FSMContext,
    lang: str,
):
    text_config = await get_config_lang(lang)
    tg_id = callback_data.tg_id
    user_info = await db.get_user(tg_id)
    if user_info is None:
        await callback.answer(text_config["admin_text"]["error_user_not_found"], show_alert=True)
        return
    subscription_data = user_info.get("subscription_data") or {}
    if not subscription_data.get("wait_sub_confirmation"):
        await callback.answer(text_config["admin_text"]["user_not_wait_confirm"], show_alert=True)
        return

    await state.update_data(tg_id=tg_id, wait_confirm_from_list=True)
    await callback.answer()
    user_clean = _user_doc_for_template(user_info)
    is_subscriber = subscription_data.get("subscription")
    if not is_subscriber:
        kb = await positive_proccess_search_wait_confirm_user_kb(
            lang,
            from_wait_list=True,
        )
    else:
        kb = await positive_proccess_search_wait_confirm_user_kb_with_subscription(
            lang,
            from_wait_list=True,
        )
    await safe_edit_message(
        callback,
        _format_admin_user_text_by_template(user_clean, text_config),
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data == "search_by_username_id")
async def search_by_username_id(callback: CallbackQuery, state: FSMContext, lang: str):
    """Обработка нажатия на кнопку "Ввести username или ID пользователя"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    text_config = await get_config_lang(lang)
    text = text_config["admin_text"]["search_by_username_id"]

    await state.update_data(wait_confirm_from_list=False)
    await state.set_state(AdminStates.wait_confirm_user)

    await safe_edit_message(
        callback,
        text,
        reply_markup=(await search_wait_confirm_user_kb(user_id, lang)).as_markup())
    logger.info(f"Пользователь {user_id} ({username}) ищет пользователя ")

@router.message(AdminStates.wait_confirm_user, F.text)
async def process_search_by_username_id(message: Message, state: FSMContext, lang: str):
    """Админ прислал username или id пользователя, ожидающего подтверждение"""
    username_id = message.text.strip()

    admin_user_id = message.from_user.id
    admin_username = message.from_user.username or ""
    
    text_config = await get_config_lang(lang)

    await state.update_data(username_id=username_id, wait_confirm_from_list=False)

    user_info_by_username_id = await db.get_user_by_username_or_id(username_id)
    if user_info_by_username_id is None:
        user_not_search = text_config["admin_text"]["user_not_search"]
        await message.answer(
            text=user_not_search,
            reply_markup=(await search_wait_confirm_user_kb(admin_user_id, lang)).as_markup(),
        )
        logger.info(f"Админ {admin_user_id} ({admin_username}) не нашел пользователя {username_id}")
        return

    subscription_data = user_info_by_username_id.get("subscription_data") or {}
    wait_confirm = subscription_data.get("wait_sub_confirmation")
    is_subscriber = subscription_data.get("subscription")

    if wait_confirm and not is_subscriber:
        await state.update_data(tg_id=user_info_by_username_id.get("tg_id"))
        await message.answer(
            _format_admin_user_text_by_template(user_info_by_username_id, text_config),
            reply_markup=(
                await positive_proccess_search_wait_confirm_user_kb(
                    lang,
                    from_wait_list=await _wait_confirm_kb_from_list(state),
                )
            ).as_markup(),
        )
    elif wait_confirm and is_subscriber:
        await state.update_data(tg_id=user_info_by_username_id.get("tg_id"))
        await message.answer(
            _format_admin_user_text_by_template(user_info_by_username_id, text_config),
            reply_markup=(
                await positive_proccess_search_wait_confirm_user_kb_with_subscription(
                    lang,
                    from_wait_list=await _wait_confirm_kb_from_list(state),
                )
            ).as_markup(),
        )
    else:
        user_not_wait_confirm = text_config["admin_text"]["user_not_wait_confirm"]
        await message.answer(
            text=user_not_wait_confirm,
            reply_markup=(await search_wait_confirm_user_kb(admin_user_id, lang)).as_markup(),
        )
    logger.info(f"Админ {admin_user_id} ({admin_username}) ищет пользователя {username_id}")

@router.callback_query(F.data == "confirm_subscription")
async def confirm_subscription(callback: CallbackQuery, state: FSMContext, lang: str):
    """Админ подтверждает подписку пользователю и окно обновляется свежими данными."""
    await callback.answer()
    
    admin_user_id = callback.from_user.id
    admin_username = callback.from_user.username or ""
    text_config = await get_config_lang(lang)

    data = await state.get_data()

    username_id = data.get("tg_id")
    if username_id is None:
        error_search_user = text_config["admin_text"]["error_search_user"]
        await callback.answer(error_search_user, show_alert=True)
        return

    user_info_by_username_id = await db.get_user_by_username_or_id(username_id)
    tg_id = user_info_by_username_id.get("tg_id")
    subscription_data = user_info_by_username_id.get("subscription_data")
    wait_confirm = subscription_data.get("wait_sub_confirmation")

    if not wait_confirm:
        user_not_wait_confirm = text_config["admin_text"]["user_not_wait_confirm"]
        await safe_edit_message(
            callback,
            text=user_not_wait_confirm,
            reply_markup=(await search_wait_confirm_user_kb(admin_user_id, lang)).as_markup(),
        )
        return
    else:
        try:
            await db.admin_check_subscription(int(username_id))
        except (ValidationError, UsersRepositoryError) as e:
            await callback.answer(f"Не удалось подтвердить: {e}", show_alert=True)
            return

        user = await db.get_user(int(tg_id))
        if user is None:
            error_user_not_found = text_config["admin_text"]["error_user_not_found"]
            await callback.answer(error_user_not_found, show_alert=True)
            return

        await safe_edit_message(
            callback,
            _format_admin_user_text_by_template(_user_doc_for_template(user), text_config),
            reply_markup=(
                await positive_proccess_search_wait_confirm_user_kb(
                    lang,
                    from_wait_list=await _wait_confirm_kb_from_list(state),
                )
            ).as_markup(),
        )
        await _notify_user_payment_status(callback.bot, user, "payment_confirmed")
        logger.info(f"Админ {admin_user_id} ({admin_username}) подтвердил подписку пользователю {username_id}")

@router.callback_query(F.data == "admin_prolong_subscription")
async def prolong_subscription(callback: CallbackQuery, state: FSMContext, lang: str):
    """Админ продлевает подписку пользователю и окно обновляется свежими данными."""
    await callback.answer()

    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    text_config = await get_config_lang(lang)

    data = await state.get_data()
    username_id = data.get("tg_id")
    if username_id is None:
        error_search_user = text_config["admin_text"]["error_search_user"]
        await callback.answer(error_search_user, show_alert=True)
        return

    user_info_by_username_id = await db.get_user_by_username_or_id(username_id)
    tg_id = user_info_by_username_id.get("tg_id")
    subscription_data = user_info_by_username_id.get("subscription_data")
    wait_confirm = subscription_data.get("wait_sub_confirmation")

    if not wait_confirm:
        user_not_wait_confirm = text_config["admin_text"]["user_not_wait_confirm"]
        await safe_edit_message(
            callback,
            text=user_not_wait_confirm,
            reply_markup=(await search_wait_confirm_user_kb(user_id, lang)).as_markup(),
        )
        return
    else:
        try:
            await db.admin_prolong_subscription(int(tg_id))
        except (ValidationError, UsersRepositoryError) as e:
            await callback.answer(f"Не удалось продлить: {e}", show_alert=True)
            return

        user = await db.get_user(int(tg_id))
        if user is None:
            error_user_not_found = text_config["admin_text"]["error_user_not_found"]
            await callback.answer(error_user_not_found, show_alert=True)
            return

        await safe_edit_message(
            callback,
            _format_admin_user_text_by_template(_user_doc_for_template(user), text_config),
            reply_markup=(
                await positive_proccess_search_wait_confirm_user_kb_with_subscription(
                    lang,
                    from_wait_list=await _wait_confirm_kb_from_list(state),
                )
            ).as_markup(),
        )
        await _notify_user_payment_status(callback.bot, user, "prolong_confirmed")
        logger.info(f"Админ {user_id} ({username}) продлил подписку пользователю {username_id}")

@router.callback_query(F.data == "cancel_prolong_subscription")
async def cancel_prolong_subscription(callback: CallbackQuery, state: FSMContext, lang: str):
    """Админ отклоняет продление подписки пользователю и окно обновляется свежими данными."""
    await callback.answer()

    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    text_config = await get_config_lang(lang)

    data = await state.get_data()
    username_id = data.get("tg_id")
    if username_id is None:
        error_search_user = text_config["admin_text"]["error_search_user"]
        await callback.answer(error_search_user, show_alert=True)
        return
    
    user_info_by_username_id = await db.get_user_by_username_or_id(username_id)
    tg_id = user_info_by_username_id.get("tg_id")

    try:
        await db.admin_cancel_prolong_subscription(int(tg_id))
    except (ValidationError, UsersRepositoryError) as e:
        await callback.answer(f"Не удалось отклонить: {e}", show_alert=True)
        return

    user = await db.get_user(int(tg_id))
    if user is None:
        error_user_not_found = text_config["admin_text"]["error_user_not_found"]
        await callback.answer(error_user_not_found, show_alert=True)
        return

    await safe_edit_message(
        callback,
        _format_admin_user_text_by_template(_user_doc_for_template(user), text_config),
        reply_markup=(
            await positive_proccess_search_wait_confirm_user_kb_with_subscription(
                lang,
                from_wait_list=await _wait_confirm_kb_from_list(state),
            )
        ).as_markup(),
    )
    await _notify_user_payment_status(callback.bot, user, "prolong_rejected")

    logger.info(f"Админ {user_id} ({username}) отклонил продление подписки пользователю {username_id}")

@router.callback_query(F.data == "cancel_subscription")
async def cancel_subscription(callback: CallbackQuery, state: FSMContext, lang: str):
    """Админ отменяет подписку пользователю и окно обновляется свежими данными."""
    await callback.answer()

    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    text_config = await get_config_lang(lang)

    data = await state.get_data()
    username_id = data.get("tg_id")
    if username_id is None:
        error_search_user = text_config["admin_text"]["error_search_user"]
        await callback.answer(error_search_user, show_alert=True)
        return
    
    user_info_by_username_id = await db.get_user_by_username_or_id(username_id)
    tg_id = user_info_by_username_id.get("tg_id")
    
    try:
        await db.admin_cancel_subscription(int(tg_id))
    except (ValidationError, UsersRepositoryError) as e:
        await callback.answer(f"Не удалось отменить: {e}", show_alert=True)
        return

    user = await db.get_user(int(tg_id))
    if user is None:
        error_user_not_found = text_config["admin_text"]["error_user_not_found"]
        await callback.answer(error_user_not_found, show_alert=True)
        return

    await safe_edit_message(
        callback,
        _format_admin_user_text_by_template(_user_doc_for_template(user), text_config),
        reply_markup=(
            await positive_proccess_search_wait_confirm_user_kb(
                lang,
                from_wait_list=await _wait_confirm_kb_from_list(state),
            )
        ).as_markup(),
    )
    await _notify_user_payment_status(callback.bot, user, "payment_rejected")

    logger.info(f"Админ {user_id} ({username}) отклонил подписку пользователю {username_id}")

# -------------------------------------------------------------
# Подписчики
# -------------------------------------------------------------

@router.callback_query(F.data == "subscribers")
async def subscribers(callback: CallbackQuery, lang: str):
    """Обработка нажатия на кнопку "Подписчики"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    text_config = await get_config_lang(lang)
    text = text_config["admin_text"]["subscribers"]

    await safe_edit_message(
        callback,
        text,
        reply_markup=(await subscribers_kb(user_id, lang)).as_markup())
    logger.info(f"Пользователь {user_id} ({username}) открыл выбор метода поиска подписчиков")


async def _render_subscribers_list(callback: CallbackQuery, state: FSMContext, lang: str, page: int) -> None:
    await state.update_data(subscribers_from_list=False)
    text_config = await get_config_lang(lang)
    try:
        total = await db.count_subscribers()
    except UsersRepositoryError as e:
        await callback.answer(str(e), show_alert=True)
        return
    if total == 0:
        text = text_config["admin_text"]["subscribers_list_empty"]
        entries: list[dict[str, Any]] = []
        page = 0
    else:
        pages = max(1, (total + ADMIN_LIST_PAGE_SIZE - 1) // ADMIN_LIST_PAGE_SIZE)
        page = max(0, min(page, pages - 1))
        skip = page * ADMIN_LIST_PAGE_SIZE
        try:
            entries = await db.list_subscribers(skip, ADMIN_LIST_PAGE_SIZE)
        except UsersRepositoryError as e:
            await callback.answer(str(e), show_alert=True)
            return
        text = text_config["admin_text"]["subscribers_list_title"].format(
            page=page + 1,
            pages=pages,
            total=total,
        )
    await callback.answer()
    await safe_edit_message(
        callback,
        text,
        reply_markup=(await subscribers_list_page_kb(entries, page, total, lang)).as_markup(),
    )


@router.callback_query(F.data == "subscribers_list")
async def subscribers_list_open(callback: CallbackQuery, state: FSMContext, lang: str):
    """Список подписчиков с пагинацией."""
    await _render_subscribers_list(callback, state, lang, 0)


@router.callback_query(SubscribersListPageCb.filter())
async def subscribers_list_page(callback: CallbackQuery, callback_data: SubscribersListPageCb, state: FSMContext, lang: str):
    await _render_subscribers_list(callback, state, lang, callback_data.page)


@router.callback_query(SubscribersUserCb.filter())
async def subscribers_list_pick_user(
    callback: CallbackQuery,
    callback_data: SubscribersUserCb,
    state: FSMContext,
    lang: str,
):
    text_config = await get_config_lang(lang)
    tg_id = callback_data.tg_id
    user_info = await db.get_user(tg_id)
    if user_info is None:
        await callback.answer(text_config["admin_text"]["error_user_not_found"], show_alert=True)
        return
    subscription_data = user_info.get("subscription_data") or {}
    if not subscription_data.get("subscription"):
        await callback.answer(text_config["admin_text"]["user_not_subscriber"], show_alert=True)
        return

    await state.update_data(username_id=tg_id, subscribers_from_list=True)
    await callback.answer()
    await _render_subscriber_card(
        callback,
        user_info,
        state,
        lang,
        from_subscribers_list=True,
    )


@router.callback_query(F.data == "search_subscribers_by_username_id")
async def search_subscribers_by_username_id(callback: CallbackQuery, state: FSMContext, lang: str):
    """Обработка нажатия на кнопку "Ввести username или ID подписчика"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    text_config = await get_config_lang(lang)
    text = text_config["admin_text"]["search_subscribers_by_username_id"]

    await state.update_data(subscribers_from_list=False)
    await state.set_state(AdminStates.subscribers_user)

    await safe_edit_message(
        callback,
        text,
        reply_markup=(await search_subscribers_kb(user_id, lang)).as_markup())
    logger.info(f"Пользователь {user_id} ({username}) ищет подписчика ")

@router.message(AdminStates.subscribers_user, F.text)
async def process_search_subscribers_by_username_id(message: Message, state: FSMContext, lang: str):
    """Админ прислал username или id подписчика"""
    username_id = message.text.strip()
    
    admin_user_id = message.from_user.id
    admin_username = message.from_user.username or ""
    
    text_config = await get_config_lang(lang)
    
    user_info_by_username_id = await db.get_user_by_username_or_id(username_id)
    if user_info_by_username_id is None:
        user_not_search = text_config["admin_text"]["user_not_search"]
        await message.answer(
            text=user_not_search,
            reply_markup=(await search_subscribers_kb(admin_user_id, lang)).as_markup(),
        )
        logger.info(f"Админ {admin_user_id} ({admin_username}) не нашел пользователя {username_id}")
        return
    tg_id = user_info_by_username_id.get("tg_id")

    await state.update_data(username_id=tg_id, subscribers_from_list=False)

    subscription_data = user_info_by_username_id.get("subscription_data")
    is_subscriber = subscription_data.get("subscription")

    if is_subscriber:
        await _render_subscriber_card(
            message,
            user_info_by_username_id,
            state,
            lang,
            from_subscribers_list=await _subscribers_kb_from_list(state),
            edit=False,
        )
    else:
        user_not_subscriber = text_config["admin_text"]["user_not_subscriber"]
        await message.answer(
            text=user_not_subscriber,
            reply_markup=(await search_subscribers_kb(admin_user_id, lang)).as_markup(),
        )
        logger.info(f"Админ {admin_user_id} ({admin_username}) не нашел подписчика {username_id}")
        return

@router.callback_query(F.data == "subscribers_settings_main")
async def subscribers_settings_main(callback: CallbackQuery, state: FSMContext, lang: str):
    """Админ устанавливает основные настройки подписки пользователю"""

    admin_user_id = callback.from_user.id
    admin_username = callback.from_user.username or ""

    text_config = await get_config_lang(lang)
    
    data = await state.get_data()
    tg_id = data.get("username_id")
    if tg_id is None:
        error_search_user = text_config["admin_text"]["error_search_user"]
        await callback.answer(error_search_user, show_alert=True)
        return
    
    user_info_by_username_id = await db.get_user_by_username_or_id(tg_id)
    subscription_data = user_info_by_username_id.get("subscription_data")
    is_subscriber = subscription_data.get("subscription")

    if is_subscriber:
        await callback.answer()
        await _render_subscriber_card(
            callback,
            user_info_by_username_id,
            state,
            lang,
            from_subscribers_list=await _subscribers_kb_from_list(state),
        )
    else:
        user_not_subscriber = text_config["admin_text"]["user_not_subscriber"]
        await safe_edit_message(
            callback,
            text=user_not_subscriber,
            reply_markup=(await search_subscribers_kb(admin_user_id, lang)).as_markup(),
        )
        logger.info(f"Админ {admin_user_id} ({admin_username}) не нашел подписчика {tg_id}")
        return


@router.callback_query(F.data == "admin_toggle_unlimited_trade_amount")
async def admin_toggle_unlimited_trade_amount(callback: CallbackQuery, state: FSMContext, lang: str):
    """Включить/выключить расширенный режим суммы сделки для подписчика."""
    text_config = await get_config_lang(lang)
    data = await state.get_data()
    tg_id = data.get("username_id")
    if tg_id is None:
        await callback.answer(text_config["admin_text"]["error_search_user"], show_alert=True)
        return

    user_info = await db.get_user(int(tg_id))
    if user_info is None:
        await callback.answer(text_config["admin_text"]["error_user_not_found"], show_alert=True)
        return

    try:
        is_unlimited = await app_settings_db.is_unlimited_trade_amount(int(tg_id))
        if is_unlimited:
            await app_settings_db.remove_unlimited_trade_amount(int(tg_id))
            notice = text_config["admin_text"]["toggle_unlimited_trade_removed"]
        else:
            await app_settings_db.add_unlimited_trade_amount(int(tg_id))
            notice = text_config["admin_text"]["toggle_unlimited_trade_added"]
    except AppSettingsRepositoryError as e:
        await callback.answer(str(e), show_alert=True)
        return

    await callback.answer(notice, show_alert=True)
    await _render_subscriber_card(
        callback,
        user_info,
        state,
        lang,
        from_subscribers_list=await _subscribers_kb_from_list(state),
    )


@router.callback_query(F.data == "subscription_settings")
async def subscription_settings(callback: CallbackQuery, state: FSMContext, lang: str):
    """Админ устанавливает настройки подписки пользователю"""

    admin_user_id = callback.from_user.id
    admin_username = callback.from_user.username or ""
    text_config = await get_config_lang(lang)
    
    data = await state.get_data()
    username_id = data.get("username_id")
    if username_id is None:
        error_search_user = text_config["admin_text"]["error_search_user"]
        await callback.answer(error_search_user, show_alert=True)
        return

    user_info_by_username_id = await db.get_user_by_username_or_id(username_id)
    tg_id = user_info_by_username_id.get("tg_id")
    subscription_data = user_info_by_username_id.get("subscription_data")
    is_subscriber = subscription_data.get("subscription")

    if is_subscriber:
        await safe_edit_message(
            callback,
            _format_admin_subscribers_text_by_template(user_info_by_username_id, text_config, "subscription_settings"),
            reply_markup=(await subscription_settings_kb(tg_id, lang)).as_markup(),
        )
    else:
        user_not_subscriber = text_config["admin_text"]["user_not_subscriber"]
        await safe_edit_message(
            callback,
            text=user_not_subscriber,
            reply_markup=(await search_subscribers_kb(tg_id, lang)).as_markup(),
        )
        logger.info(f"Админ {admin_user_id} ({admin_username}) не нашел подписчика {username_id}")
        return

@router.callback_query(F.data == "bybit_settings")
async def bybit_settings(callback: CallbackQuery, state: FSMContext, lang: str):
    """Админ устанавливает настройки подписки пользователю"""

    admin_user_id = callback.from_user.id
    admin_username = callback.from_user.username or ""
    text_config = await get_config_lang(lang)
    
    data = await state.get_data()
    username_id = data.get("username_id")
    if username_id is None:
        error_search_user = text_config["admin_text"]["error_search_user"]
        await callback.answer(error_search_user, show_alert=True)
        return

    user_info_by_username_id = await db.get_user_by_username_or_id(username_id)
    subscription_data = user_info_by_username_id.get("subscription_data")
    is_subscriber = subscription_data.get("subscription")

    if is_subscriber:
        await safe_edit_message(
            callback,
            _format_admin_subscribers_text_by_template(user_info_by_username_id, text_config, "bybit_settings"),
            reply_markup=(await bybit_settings_kb(username_id, lang)).as_markup(),
        )
    else:
        user_not_subscriber = text_config["admin_text"]["user_not_subscriber"]
        await safe_edit_message(
            callback,
            text=user_not_subscriber,
            reply_markup=(await search_subscribers_kb(username_id, lang)).as_markup(),
        )
        logger.info(f"Админ {admin_user_id} ({admin_username}) не нашел подписчика {username_id}")
        return


@router.callback_query(F.data == "edit_api_key")
async def edit_api_key(callback: CallbackQuery, state: FSMContext, lang: str):
    """Админ меняет API ключ подписчика."""
    admin_user_id = callback.from_user.id
    admin_username = callback.from_user.username or ""
    text_config = await get_config_lang(lang)

    data = await state.get_data()
    username_id = data.get("username_id")
    if username_id is None:
        await callback.answer(text_config["admin_text"]["error_search_user"], show_alert=True)
        return

    await state.set_state(AdminStates.edit_bybit_api_key)
    await callback.answer()
    await safe_edit_message(
        callback,
        text_config["admin_text"]["edit_api_key"],
        reply_markup=(await back_to_bybit_settings_kb(username_id, lang)).as_markup(),
    )
    logger.info(
        f"Админ {admin_user_id} ({admin_username}) начал смену API ключа пользователя {username_id}"
    )


@router.callback_query(F.data == "edit_api_secret")
async def edit_api_secret(callback: CallbackQuery, state: FSMContext, lang: str):
    """Админ меняет API secret подписчика."""
    admin_user_id = callback.from_user.id
    admin_username = callback.from_user.username or ""
    text_config = await get_config_lang(lang)

    data = await state.get_data()
    username_id = data.get("username_id")
    if username_id is None:
        await callback.answer(text_config["admin_text"]["error_search_user"], show_alert=True)
        return

    await state.set_state(AdminStates.edit_bybit_api_secret)
    await callback.answer()
    await safe_edit_message(
        callback,
        text_config["admin_text"]["edit_api_secret"],
        reply_markup=(await back_to_bybit_settings_kb(username_id, lang)).as_markup(),
    )
    logger.info(
        f"Админ {admin_user_id} ({admin_username}) начал смену API secret пользователя {username_id}"
    )


@router.callback_query(F.data == "edit_sum_for_trades")
async def edit_sum_for_trades(callback: CallbackQuery, state: FSMContext, lang: str):
    """Админ меняет сумму сделки подписчика."""
    admin_user_id = callback.from_user.id
    admin_username = callback.from_user.username or ""
    text_config = await get_config_lang(lang)

    data = await state.get_data()
    username_id = data.get("username_id")
    if username_id is None:
        await callback.answer(text_config["admin_text"]["error_search_user"], show_alert=True)
        return

    await state.set_state(AdminStates.edit_bybit_sum_for_trades)
    await callback.answer()
    await safe_edit_message(
        callback,
        text_config["admin_text"]["edit_sum_for_trades"],
        reply_markup=(await back_to_bybit_settings_kb(username_id, lang)).as_markup(),
    )
    logger.info(
        f"Админ {admin_user_id} ({admin_username}) начал смену суммы сделки пользователя {username_id}"
    )


@router.callback_query(F.data == "edit_stop_trades")
async def edit_stop_trades(callback: CallbackQuery, state: FSMContext, lang: str):
    """Переключение остановки торговли у подписчика."""
    admin_user_id = callback.from_user.id
    admin_username = callback.from_user.username or ""
    text_config = await get_config_lang(lang)

    data = await state.get_data()
    username_id = data.get("username_id")
    if username_id is None:
        await callback.answer(text_config["admin_text"]["error_search_user"], show_alert=True)
        return

    tg_id = int(username_id)
    user = await db.get_user(tg_id)
    if user is None:
        await callback.answer(text_config["admin_text"]["error_user_not_found"], show_alert=True)
        return

    bybit_data = user.get("bybit_data") or {}
    current_stop = bybit_data.get("stop_trading") is True
    try:
        await db.update_stop_trading(tg_id, not current_stop)
    except (ValidationError, UsersRepositoryError) as e:
        await callback.answer(f"Не удалось обновить: {e}", show_alert=True)
        return

    await callback.answer()

    user_info = await db.get_user_by_username_or_id(tg_id)
    if user_info is None:
        logger.error("После update_stop_trading пользователь tg_id=%s не найден", tg_id)
        return

    await safe_edit_message(
        callback,
        _format_admin_subscribers_text_by_template(user_info, text_config, "bybit_settings"),
        reply_markup=(await bybit_settings_kb(tg_id, lang)).as_markup(),
    )
    logger.info(
        f"Админ {admin_user_id} ({admin_username}) изменил stop_trading пользователя {tg_id} -> {not current_stop}"
    )


@router.message(AdminStates.edit_bybit_api_key, F.text)
async def process_edit_api_key(message: Message, state: FSMContext, lang: str):
    """Админ ввёл новый API ключ."""
    admin_user_id = message.from_user.id
    admin_username = message.from_user.username or ""
    text_config = await get_config_lang(lang)

    data = await state.get_data()
    username_id = data.get("username_id")
    if username_id is None:
        await message.answer(text_config["admin_text"]["error_search_user"])
        await state.clear()
        return

    tg_id = int(username_id)
    value = message.text.strip()
    try:
        await db.update_api_key(tg_id, value)
    except (ValidationError, UsersRepositoryError) as e:
        await message.answer(f"Не удалось обновить API ключ: {e}")
        return

    await state.set_state(None)
    await message.answer(
        text_config["admin_text"]["edit_api_key_success"],
        reply_markup=(await back_to_bybit_settings_kb(tg_id, lang)).as_markup(),
    )
    logger.info(
        f"Админ {admin_user_id} ({admin_username}) обновил API ключ пользователя {tg_id}"
    )


@router.message(AdminStates.edit_bybit_api_secret, F.text)
async def process_edit_api_secret(message: Message, state: FSMContext, lang: str):
    """Админ ввёл новый API secret."""
    admin_user_id = message.from_user.id
    admin_username = message.from_user.username or ""
    text_config = await get_config_lang(lang)

    data = await state.get_data()
    username_id = data.get("username_id")
    if username_id is None:
        await message.answer(text_config["admin_text"]["error_search_user"])
        await state.clear()
        return

    tg_id = int(username_id)
    value = message.text.strip()
    try:
        await db.update_api_secret(tg_id, value)
    except (ValidationError, UsersRepositoryError) as e:
        await message.answer(f"Не удалось обновить API secret: {e}")
        return

    await state.set_state(None)
    await message.answer(
        text_config["admin_text"]["edit_api_secret_success"],
        reply_markup=(await back_to_bybit_settings_kb(tg_id, lang)).as_markup(),
    )
    logger.info(
        f"Админ {admin_user_id} ({admin_username}) обновил API secret пользователя {tg_id}"
    )


@router.message(AdminStates.edit_bybit_sum_for_trades, F.text)
async def process_edit_sum_for_trades(message: Message, state: FSMContext, lang: str):
    """Админ ввёл новую сумму сделки (строка, как в репозитории)."""
    admin_user_id = message.from_user.id
    admin_username = message.from_user.username or ""
    text_config = await get_config_lang(lang)

    data = await state.get_data()
    username_id = data.get("username_id")
    if username_id is None:
        await message.answer(text_config["admin_text"]["error_search_user"])
        await state.clear()
        return

    tg_id = int(username_id)
    value = message.text.strip()
    try:
        await db.update_sum_for_trades(tg_id, value)
    except (ValidationError, UsersRepositoryError) as e:
        await message.answer(f"Не удалось обновить сумму: {e}")
        return

    await state.set_state(None)
    await message.answer(
        text_config["admin_text"]["edit_sum_for_trades_success"].format(sum_for_trades=value),
        reply_markup=(await back_to_bybit_settings_kb(tg_id, lang)).as_markup(),
    )
    logger.info(
        f"Админ {admin_user_id} ({admin_username}) обновил sum_for_trades пользователя {tg_id}"
    )


@router.callback_query(F.data == "statistics_info")
async def statistics_info(callback: CallbackQuery, state: FSMContext, lang: str):
    """Админ устанавливает настройки подписки пользователю"""

    admin_user_id = callback.from_user.id
    admin_username = callback.from_user.username or ""
    text_config = await get_config_lang(lang)
    
    data = await state.get_data()
    username_id = data.get("username_id")
    if username_id is None:
        error_search_user = text_config["admin_text"]["error_search_user"]
        await callback.answer(error_search_user, show_alert=True)
        return

    user_info_by_username_id = await db.get_user_by_username_or_id(username_id)
    subscription_data = user_info_by_username_id.get("subscription_data")
    is_subscriber = subscription_data.get("subscription")

    if is_subscriber:
        await safe_edit_message(
            callback,
            _format_admin_subscribers_text_by_template(user_info_by_username_id, text_config, "statistics_info"),
            reply_markup=(await statistics_info_kb(username_id, lang)).as_markup(),
        )
    else:
        user_not_subscriber = text_config["admin_text"]["user_not_subscriber"]
        await safe_edit_message(
            callback,
            text=user_not_subscriber,
            reply_markup=(await search_subscribers_kb(username_id, lang)).as_markup(),
        )
        logger.info(f"Админ {admin_user_id} ({admin_username}) не нашел подписчика {username_id}")
        return

@router.callback_query(F.data == "edit_subscription_mode")
async def edit_subscription_mode(callback: CallbackQuery, state: FSMContext, lang: str):
    """Админ устанавливает настройки подписки пользователю"""

    admin_user_id = callback.from_user.id
    admin_username = callback.from_user.username or ""
    text_config = await get_config_lang(lang)
    
    data = await state.get_data()
    username_id = data.get("username_id")
    if username_id is None:
        error_search_user = text_config["admin_text"]["error_search_user"]
        await callback.answer(error_search_user, show_alert=True)
        return
    
    subscription_status = await db.get_subscription_status(username_id)
    if subscription_status:
        await db.update_subscription(username_id, False)
    else:
        await db.update_subscription(username_id, True)
    
    user_info_by_username_id = await db.get_user_by_username_or_id(username_id)
    await safe_edit_message(
        callback,
        _format_admin_subscribers_text_by_template(user_info_by_username_id, text_config, "subscription_settings"),
        reply_markup=(await subscription_settings_kb(username_id, lang)).as_markup(),
    )
    logger.info(f"Админ {admin_user_id} ({admin_username}) изменил состояние подписки пользователя {username_id}")

@router.callback_query(F.data == "edit_date_end_subs")
async def edit_date_end_subs(callback: CallbackQuery, state: FSMContext, lang: str):
    """Админ устанавливает настройки подписки подписчику (дата окончания подписки)"""

    admin_user_id = callback.from_user.id
    admin_username = callback.from_user.username or ""
    text_config = await get_config_lang(lang)
    
    data = await state.get_data()
    username_id = data.get("username_id")
    if username_id is None:
        error_search_user = text_config["admin_text"]["error_search_user"]
        await callback.answer(error_search_user, show_alert=True)
        return

    await state.set_state(AdminStates.edit_end_subscription_date)
    await callback.answer()
    await safe_edit_message(
        callback,
        text_config["admin_text"]["edit_date_end_subs"],
        reply_markup=(await back_to_subscription_settings_kb(username_id, lang)).as_markup(),
    )
    logger.info(
        f"Админ {admin_user_id} ({admin_username}) начал изменение даты окончания подписки пользователя {username_id}"
    )


@router.message(AdminStates.edit_end_subscription_date, F.text)
async def process_edit_date_end_subs(message: Message, state: FSMContext, lang: str):
    """Админ вводит новую дату окончания подписки в формате yyyy.mm.dd. hh.mm.ss."""
    admin_user_id = message.from_user.id
    admin_username = message.from_user.username or ""
    text_config = await get_config_lang(lang)

    data = await state.get_data()
    username_id = data.get("username_id")
    if username_id is None:
        await message.answer(text_config["admin_text"]["error_search_user"])
        await state.clear()
        return

    date_text = message.text.strip()
    try:
        end_subscription_date = await db.update_end_subscription_date_from_string(username_id, date_text)
    except ValidationError:
        await message.answer(
            text_config["admin_text"]["edit_date_end_subs_invalid_format"],
            reply_markup=(await subscription_settings_kb(username_id, lang)).as_markup(),
        )
        return
    except UsersRepositoryError as e:
        await message.answer(f"Не удалось обновить дату: {e}")
        return

    user_info = await db.get_user_by_username_or_id(username_id)
    if user_info is None:
        await message.answer(text_config["admin_text"]["error_user_not_found"])
        return

    await message.answer(
        text_config["admin_text"]["edit_date_end_subs_success"].format(
            end_subscription_date=end_subscription_date.strftime("%Y-%m-%d %H:%M:%S")
        ),
        reply_markup=(await back_to_subscription_settings_kb(username_id, lang)).as_markup(),
    )
    logger.info(
        f"Админ {admin_user_id} ({admin_username}) изменил дату окончания подписки пользователя {username_id} "
        f"на {end_subscription_date.isoformat()}"
    )

# -------------------------------------------------------------
# Сервер
# -------------------------------------------------------------

@router.callback_query(F.data == "server")
async def server(callback: CallbackQuery, lang: str):
    """Обработка нажатия на кнопку "Сервер"""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    text_config = await get_config_lang(lang)
    text = text_config["admin_text"]["server"]
    await safe_edit_message(
        callback,
        text,
        reply_markup=(await server_kb(user_id, lang)).as_markup())
    logger.info(f"Пользователь {user_id} ({username}) открыл сервер")

@router.callback_query(F.data == "check_health")
async def check_health(callback: CallbackQuery, lang: str):
    """Проверка работоспособности сервера."""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    text_config = await get_config_lang(lang)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{LOCAL_SERVER_URL}/health",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as response:
                data = await response.json()
                status = data.get("status", "unknown")
                service = data.get("service", "N/A")
                if response.status == 200:
                    text = text_config["admin_text"]["check_health_success"].format(
                        status=status,
                        service=service,
                    )
                else:
                    text = text_config["admin_text"]["check_health_error"].format(
                        status=status,
                    )
    except aiohttp.ClientError as e:
        text = text_config["admin_text"]["check_health_error"].format(
            status=e,
        )
        logger.error("Ошибка проверки здоровья сервера: %s", e, exc_info=True)
    except Exception as e:
        text = text_config["admin_text"]["check_health_error"].format(
            status=e,
        )
        logger.error("Неожиданная ошибка при проверке здоровья: %s", e, exc_info=True)

    await safe_edit_message(
        callback,
        text,
        reply_markup=(await back_to_server_kb(user_id, lang)).as_markup(),
    )
    await callback.answer()
    logger.info(f"Пользователь {user_id} ({username}) выполнил проверку сервера")
