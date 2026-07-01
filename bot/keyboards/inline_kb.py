from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.languages._lang_func import get_config_lang
from bot.callback_data.admin_lists import (
    ADMIN_LIST_PAGE_SIZE,
    ActiveTradeItemCb,
    ActiveTradesPageCb,
    AdminCancelProlongSubscriptionCb,
    AdminCancelSubscriptionCb,
    AdminConfirmSubscriptionCb,
    AdminProlongSubscriptionCb,
    HISTORY_TRADES_PAGE_SIZE,
    HistoryTradeItemCb,
    HistoryTradesPageCb,
    SubscribersListPageCb,
    SubscribersUserCb,
    WaitConfirmListPageCb,
    WaitConfirmUserCb,
)
from database.users_repository import db
from database.app_settings_repository import app_settings_db
from config import URL_TGCHANNEL, URL_TECH_SUPPORT


def _admin_list_user_button_text(name: str, tg_id: int) -> str:
    """Текст кнопки пользователя (лимит Telegram 64 символа)."""
    nm = name if name else "—"
    tid = str(tg_id)
    base = f"{nm} | {tid}"
    if len(base) <= 64:
        return base
    reserve = len(tid) + 4
    max_nm = 64 - reserve
    if max_nm < 4:
        return tid[:64]
    trimmed = nm[:max_nm].rstrip()
    return f"{trimmed}… | {tid}"

# -------------------------------------------------------------
# Start keyboards
# -------------------------------------------------------------

def start_menu_kb(user_id: int) -> InlineKeyboardBuilder:
    """
    Стартовое меню кнопок - выбор языка у пользователя
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="Русский", callback_data="russian_lang")
    kb.button(text="English", callback_data="english_lang")
    kb.adjust(1)
    return kb

# -------------------------------------------------------------
# Subscription keyboards
# -------------------------------------------------------------

async def subscription_buy_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Меню кнопок оплаты подписки
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["subscription_btn"]["paid"], callback_data="paid")
    kb.button(text=(await get_config_lang(lang))["subscription_btn"]["question"], callback_data="question")
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="greeting")
    kb.adjust(1)
    return kb

async def prolong_subscription_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Меню кнопок продления подписки
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["subscription_btn"]["paid"], callback_data="prolong_paid")
    kb.button(text=(await get_config_lang(lang))["subscription_btn"]["question"], callback_data="prolong_question")
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="greeting")
    kb.adjust(1)
    return kb

async def question_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Меню кнопок 'Что дальше?'
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="subscription_buy")
    kb.adjust(1)
    return kb

async def prolong_question_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Меню кнопок 'Что дальше?' продления подписки
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="prolong_subscription")
    kb.adjust(1)
    return kb

async def input_payment_id_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Меню кнопок ввода ID платежа
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["subscription_btn"]["input_payment_id"], callback_data="input_payment_id")
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="subscription_buy")
    kb.adjust(1)
    return kb
    
async def prolong_input_payment_id_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Меню кнопок ввода ID платежа продления подписки
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["subscription_btn"]["input_payment_id"], callback_data="prolong_input_payment_id")
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="prolong_subscription")
    kb.adjust(1)
    return kb

async def input_payment_id_back_kb(lang: str) -> InlineKeyboardBuilder:
    """
    Кнопка "Назад" в ввод ID платежа
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="paid")
    kb.adjust(1)
    return kb

async def prolong_input_payment_id_back_kb(lang: str) -> InlineKeyboardBuilder:
    """
    Кнопка "Назад" в ввод ID платежа продления подписки
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="prolong_paid")
    kb.adjust(1)
    return kb

async def confirm_payment_kb(lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки "Да ✓" / "Нет ✗" в подтверждение платежа
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["subscription_btn"]["confirm_payment"], callback_data="confirm_payment")
    kb.button(text=(await get_config_lang(lang))["subscription_btn"]["reject_payment"], callback_data="input_payment_id")
    kb.adjust(1)
    return kb

async def prolong_confirm_payment_kb(lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки "Да ✓" / "Нет ✗" в подтверждение платежа продления подписки
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["subscription_btn"]["confirm_payment"], callback_data="prolong_confirm_payment")
    kb.button(text=(await get_config_lang(lang))["subscription_btn"]["reject_payment"], callback_data="prolong_input_payment_id")
    kb.adjust(1)
    return kb

async def confirm_payment_success_kb(lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки после успешной отправки заявки на оплату.
    """
    cfg = await get_config_lang(lang)
    kb = InlineKeyboardBuilder()
    kb.button(text=cfg["profile_btn"]["go_to_settings"], callback_data="settings_profile")
    kb.button(text=cfg["general"]["main_menu"], callback_data="greeting")
    kb.adjust(1)
    return kb


async def payment_status_notify_kb(lang: str, message_key: str) -> InlineKeyboardBuilder | None:
    """Кнопка к уведомлению пользователю о подтверждении/отклонении оплаты."""
    cfg = await get_config_lang(lang)
    kb = InlineKeyboardBuilder()

    if message_key in ("payment_confirmed", "prolong_confirmed"):
        kb.button(text=cfg["start_btn"]["personal_account"], callback_data="profile_menu")
        kb.adjust(1)
        return kb

    if message_key in ("payment_rejected", "prolong_rejected"):
        if not URL_TECH_SUPPORT:
            return None
        kb.button(text=cfg["profile_btn"]["tech_support"], url=URL_TECH_SUPPORT)
        kb.adjust(1)
        return kb

    return None


async def help_kb(lang: str) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    cfg = await get_config_lang(lang)
    kb.button(text=cfg["general"]["main_menu"], callback_data="greeting")
    kb.adjust(1)
    return kb

# -------------------------------------------------------------
# Profile keyboards
# -------------------------------------------------------------

async def profile_menu_kb_without_subscription(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """Кнопки в профиле без подписки."""
    cfg = await get_config_lang(lang)
    kb = InlineKeyboardBuilder()
    kb.button(text=cfg["profile_btn"]["subscription_buy"], callback_data="subscription_buy")
    kb.button(text=cfg["profile_btn"]["tech_support"], url=URL_TECH_SUPPORT)
    kb.button(text=cfg["general"]["main_menu"], callback_data="greeting")
    kb.adjust(1)
    return kb


async def profile_menu_wait_sub_confirmation_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """Профиль при ожидании подтверждения — только настройка API и поддержка."""
    cfg = await get_config_lang(lang)
    kb = InlineKeyboardBuilder()
    kb.button(text=cfg["profile_btn"]["setup_profile_early"], callback_data="settings_profile")
    kb.button(text=cfg["profile_btn"]["tech_support"], url=URL_TECH_SUPPORT)
    kb.button(text=cfg["general"]["main_menu"], callback_data="greeting")
    kb.adjust(1)
    return kb


async def profile_menu_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """Кнопки в профиле с активной подпиской."""
    cfg = await get_config_lang(lang)
    kb = InlineKeyboardBuilder()
    kb.button(text=cfg["profile_btn"]["settings_profile"], callback_data="settings_profile")
    kb.button(text=cfg["profile_btn"]["statistics"], callback_data="statistics")
    kb.button(text=cfg["profile_btn"]["trading"], callback_data="trading")
    kb.button(text=cfg["profile_btn"]["trading_portfolio"], callback_data="trading_portfolio")
    kb.button(text=cfg["profile_btn"]["history_trades"], callback_data="history_trades")
    kb.button(text=cfg["profile_btn"]["tech_support"], url=URL_TECH_SUPPORT)
    kb.button(text=cfg["general"]["main_menu"], callback_data="greeting")
    kb.adjust(2, 2, 1, 1)
    return kb

async def profile_statistics_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в статистике профиля
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="profile_menu")
    kb.adjust(1)
    return kb
    
async def profile_settings_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """Кнопки в настройках профиля."""
    cfg = await get_config_lang(lang)
    user = await db.get_user(user_id)
    bybit = (user or {}).get("bybit_data") or {}
    has_api = bool(str(bybit.get("api_key") or "").strip() and str(bybit.get("api_secret") or "").strip())

    kb = InlineKeyboardBuilder()
    kb.button(text=cfg["profile_btn"]["edit_api_key_secret"], callback_data="profile_settings_api_key_secret")
    if has_api:
        kb.button(text=cfg["profile_btn"]["edit_sum_for_trades"], callback_data="profile_settings_sum_for_trades")
    else:
        kb.button(
            text=cfg["profile_btn"]["edit_sum_for_trades_locked"],
            callback_data="profile_settings_sum_locked",
        )
    kb.button(text=cfg["general"]["back"], callback_data="profile_menu")
    kb.adjust(1)
    return kb

async def back_to_profile_settings_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Возвращение в настройку профиля
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="settings_profile")
    kb.adjust(1)
    return kb


async def api_key_instruction_kb(lang: str) -> InlineKeyboardBuilder:
    """Кнопки после видео-инструкции по созданию API ключа."""
    cfg = await get_config_lang(lang)
    kb = InlineKeyboardBuilder()
    kb.button(text=cfg["profile_btn"]["api_key_instruction_enter"], callback_data="profile_api_key_instruction_enter")
    kb.button(text=cfg["general"]["back"], callback_data="settings_profile")
    kb.adjust(1)
    return kb


async def profile_settings_sum_risk_kb(lang: str) -> InlineKeyboardBuilder:
    """
    Подтверждение рискованной суммы сделки.
    """
    cfg = await get_config_lang(lang)
    kb = InlineKeyboardBuilder()
    kb.button(text=cfg["profile_btn"]["confirm_risk_sum_for_trades"], callback_data="profile_settings_sum_risk_confirm")
    kb.button(text=cfg["profile_btn"]["cancel_risk_sum_for_trades"], callback_data="profile_settings_sum_risk_cancel")
    kb.button(text=cfg["general"]["back"], callback_data="settings_profile")
    kb.adjust(1)
    return kb


async def profile_balance_kb(lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в разделе баланса профиля.
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="profile_menu")
    kb.adjust(1)
    return kb


async def history_trades_page_kb(
    entries: list[dict],
    page: int,
    total: int,
    lang: str,
) -> InlineKeyboardBuilder:
    """Пагинированная история сделок пользователя."""
    cfg = await get_config_lang(lang)
    kb = InlineKeyboardBuilder()
    for idx, row in enumerate(entries):
        symbol = str(row.get("symbol") or "—")
        dt = row.get("created_at") or row.get("open_time") or row.get("close_time")
        dt_text = str(dt)[:16] if dt is not None else "—"
        kb.button(
            text=f"{symbol} | {dt_text}",
            callback_data=HistoryTradeItemCb(page=int(page), idx=int(idx)),
        )

    if total > 0:
        total_pages = max(1, (total + HISTORY_TRADES_PAGE_SIZE - 1) // HISTORY_TRADES_PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        if page > 0:
            kb.button(
                text=cfg["admin_btn"]["list_prev_page"],
                callback_data=HistoryTradesPageCb(page=page - 1),
            )
        if (page + 1) * HISTORY_TRADES_PAGE_SIZE < total:
            kb.button(
                text=cfg["admin_btn"]["list_next_page"],
                callback_data=HistoryTradesPageCb(page=page + 1),
            )

    kb.button(text=cfg["general"]["back"], callback_data="profile_menu")
    kb.adjust(1)
    return kb


async def history_trade_details_kb(page: int, lang: str) -> InlineKeyboardBuilder:
    """Кнопки на карточке сделки."""
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data=HistoryTradesPageCb(page=int(page)))
    kb.adjust(1)
    return kb


async def profile_trading_kb(lang: str) -> InlineKeyboardBuilder:
    """Меню торговли в профиле."""
    cfg = await get_config_lang(lang)
    kb = InlineKeyboardBuilder()
    kb.button(text=cfg["profile_btn"]["active_trades"], callback_data="active_trades")
    kb.button(text=cfg["profile_btn"]["stop_all_trading"], callback_data="profile_stop_all_trading")
    kb.button(text=cfg["general"]["back"], callback_data="profile_menu")
    kb.adjust(2, 1)
    return kb


async def active_trades_page_kb(
    entries: list[dict],
    page: int,
    total: int,
    lang: str,
) -> InlineKeyboardBuilder:
    """Пагинированный список активных сделок пользователя."""
    cfg = await get_config_lang(lang)
    kb = InlineKeyboardBuilder()
    for idx, row in enumerate(entries):
        symbol = str(row.get("symbol") or "—")
        dt = row.get("open_time")
        dt_text = str(dt)[:16] if dt is not None else "—"
        kb.button(
            text=f"{symbol} | {dt_text}",
            callback_data=ActiveTradeItemCb(page=int(page), idx=int(idx)),
        )

    if total > 0:
        total_pages = max(1, (total + HISTORY_TRADES_PAGE_SIZE - 1) // HISTORY_TRADES_PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        if page > 0:
            kb.button(text=cfg["admin_btn"]["list_prev_page"], callback_data=ActiveTradesPageCb(page=page - 1))
        if (page + 1) * HISTORY_TRADES_PAGE_SIZE < total:
            kb.button(text=cfg["admin_btn"]["list_next_page"], callback_data=ActiveTradesPageCb(page=page + 1))

    kb.button(text=cfg["general"]["back"], callback_data="trading")
    kb.adjust(1)
    return kb


async def active_trade_details_kb(symbol: str, page: int, lang: str) -> InlineKeyboardBuilder:
    """Кнопки в карточке активной сделки."""
    cfg = await get_config_lang(lang)
    kb = InlineKeyboardBuilder()
    kb.button(text=cfg["profile_btn"]["stop_current_trade"], callback_data=f"active_trade_stop:{symbol}")
    kb.button(text=cfg["general"]["back"], callback_data=ActiveTradesPageCb(page=int(page)))
    kb.adjust(1)
    return kb


# -------------------------------------------------------------
# Admin keyboards
# -------------------------------------------------------------

async def admin_menu_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в админ-панели
    """
    cfg = await get_config_lang(lang)
    kb = InlineKeyboardBuilder()
    kb.button(text=cfg["admin_btn"]["users_list"], callback_data="users_list")
    kb.button(text=cfg["admin_btn"]["statistics_project"], callback_data="statistics_project")
    kb.button(text=cfg["admin_btn"]["stop_all_trading"], callback_data="admin_stop_all_trading")
    kb.button(text=cfg["admin_btn"]["server"], callback_data="server")
    kb.button(text=cfg["general"]["admin_to_main_menu"], callback_data="greeting")
    kb.adjust(1)
    return kb

async def users_list_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в списке пользователей
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["admin_btn"]["wait_confirm"], callback_data="wait_confirm")
    kb.button(text=(await get_config_lang(lang))["admin_btn"]["subscribers"], callback_data="subscribers")
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="admin_menu")
    kb.adjust(1)
    return kb

async def statistics_project_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в статистике проекта
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="admin_menu")
    kb.adjust(1)
    return kb

async def server_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в сервере
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["admin_btn"]["check_health"], callback_data="check_health")
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="admin_menu")
    kb.adjust(1)
    return kb

async def back_to_server_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки при возврате в сервер
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="server")
    kb.adjust(1)
    return kb

async def wait_confirm_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в списке ожидающих подтверждения
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["admin_btn"]["wait_confirm_list"], callback_data="wait_confirm_list")
    kb.button(text=(await get_config_lang(lang))["admin_btn"]["search_by_username_id"], callback_data="search_by_username_id")
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="users_list")
    kb.adjust(1)
    return kb

async def subscribers_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в списке подписчиков
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["admin_btn"]["subscribers_list"], callback_data="subscribers_list")
    kb.button(text=(await get_config_lang(lang))["admin_btn"]["search_by_username_id"], callback_data="search_subscribers_by_username_id")
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="users_list")
    kb.adjust(1)
    return kb

async def search_wait_confirm_user_kb(user_id, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в поиске пользователей, ожидающих подтверждение
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="wait_confirm")
    kb.adjust(1)
    return kb

async def search_subscribers_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в поиске подписчиков
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="subscribers")
    kb.adjust(1)
    return kb


async def wait_confirm_list_page_kb(
    entries: list[dict],
    page: int,
    total: int,
    lang: str,
) -> InlineKeyboardBuilder:
    """Пагинированный список ожидающих подтверждения (по 10 на страницу)."""
    cfg = await get_config_lang(lang)
    kb = InlineKeyboardBuilder()
    for row in entries:
        tid = row.get("tg_id")
        if tid is None:
            continue
        nm = str(row.get("name") or "—")
        kb.button(
            text=_admin_list_user_button_text(nm, int(tid)),
            callback_data=WaitConfirmUserCb(tg_id=int(tid)),
        )
    if total > 0:
        total_pages = max(1, (total + ADMIN_LIST_PAGE_SIZE - 1) // ADMIN_LIST_PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        if page > 0:
            kb.button(
                text=cfg["admin_btn"]["list_prev_page"],
                callback_data=WaitConfirmListPageCb(page=page - 1),
            )
        if (page + 1) * ADMIN_LIST_PAGE_SIZE < total:
            kb.button(
                text=cfg["admin_btn"]["list_next_page"],
                callback_data=WaitConfirmListPageCb(page=page + 1),
            )
    kb.button(text=cfg["general"]["back"], callback_data="wait_confirm")
    kb.adjust(1)
    return kb


async def subscribers_list_page_kb(
    entries: list[dict],
    page: int,
    total: int,
    lang: str,
) -> InlineKeyboardBuilder:
    """Пагинированный список подписчиков (по 10 на страницу)."""
    cfg = await get_config_lang(lang)
    kb = InlineKeyboardBuilder()
    for row in entries:
        tid = row.get("tg_id")
        if tid is None:
            continue
        nm = str(row.get("name") or "—")
        kb.button(
            text=_admin_list_user_button_text(nm, int(tid)),
            callback_data=SubscribersUserCb(tg_id=int(tid)),
        )
    if total > 0:
        total_pages = max(1, (total + ADMIN_LIST_PAGE_SIZE - 1) // ADMIN_LIST_PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        if page > 0:
            kb.button(
                text=cfg["admin_btn"]["list_prev_page"],
                callback_data=SubscribersListPageCb(page=page - 1),
            )
        if (page + 1) * ADMIN_LIST_PAGE_SIZE < total:
            kb.button(
                text=cfg["admin_btn"]["list_next_page"],
                callback_data=SubscribersListPageCb(page=page + 1),
            )
    kb.button(text=cfg["general"]["back"], callback_data="subscribers")
    kb.adjust(1)
    return kb


async def positive_proccess_search_wait_confirm_user_kb(
    lang: str,
    *,
    target_tg_id: int,
    from_wait_list: bool = False,
) -> InlineKeyboardBuilder:
    """
    Кнопки в поиске пользователей, ожидающих подтверждение
    """
    cfg = await get_config_lang(lang)
    kb = InlineKeyboardBuilder()
    if from_wait_list:
        kb.button(
            text=cfg["admin_btn"]["back_to_user_list"],
            callback_data=WaitConfirmListPageCb(page=0),
        )
    kb.button(
        text=cfg["admin_btn"]["confirm_subscription"],
        callback_data=AdminConfirmSubscriptionCb(tg_id=int(target_tg_id)),
    )
    kb.button(
        text=cfg["admin_btn"]["cancel_subscription"],
        callback_data=AdminCancelSubscriptionCb(tg_id=int(target_tg_id)),
    )
    kb.button(text=cfg["admin_btn"]["proccess_search_wair_confirm"], callback_data="search_by_username_id")
    kb.button(text=cfg["admin_btn"]["back_to_wait_confirm_menu"], callback_data="wait_confirm")
    kb.adjust(1)
    return kb

async def positive_proccess_search_subscribers_kb(
    lang: str,
    *,
    from_subscribers_list: bool = False,
    target_tg_id: int | None = None,
) -> InlineKeyboardBuilder:
    """
    Кнопки в поиске подписчиков
    """
    cfg = await get_config_lang(lang)
    kb = InlineKeyboardBuilder()
    if from_subscribers_list:
        kb.button(
            text=cfg["admin_btn"]["back_to_user_list"],
            callback_data=SubscribersListPageCb(page=0),
        )
    kb.button(text=cfg["admin_btn"]["subscription_settings"], callback_data="subscription_settings")
    kb.button(text=cfg["admin_btn"]["bybit_settings"], callback_data="bybit_settings")
    kb.button(text=cfg["admin_btn"]["statistics_info"], callback_data="statistics_info")
    if target_tg_id is not None:
        is_unlimited = await app_settings_db.is_unlimited_trade_amount(int(target_tg_id))
        if is_unlimited:
            kb.button(
                text=cfg["admin_btn"]["toggle_unlimited_trade_remove"],
                callback_data="admin_toggle_unlimited_trade_amount",
            )
        else:
            kb.button(
                text=cfg["admin_btn"]["toggle_unlimited_trade_add"],
                callback_data="admin_toggle_unlimited_trade_amount",
            )
    kb.button(text=cfg["admin_btn"]["search_subscribers_again"], callback_data="search_subscribers_by_username_id")
    kb.button(text=cfg["admin_btn"]["back_to_subscribers_menu"], callback_data="subscribers")
    kb.adjust(1)
    return kb

async def positive_proccess_search_wait_confirm_user_kb_with_subscription(
    lang: str,
    *,
    target_tg_id: int,
    from_wait_list: bool = False,
) -> InlineKeyboardBuilder:
    """
    Кнопки в поиске пользователей, ожидающих подтверждение с подпиской
    """
    cfg = await get_config_lang(lang)
    kb = InlineKeyboardBuilder()
    if from_wait_list:
        kb.button(
            text=cfg["admin_btn"]["back_to_user_list"],
            callback_data=WaitConfirmListPageCb(page=0),
        )
    kb.button(
        text=cfg["admin_btn"]["prolong_subscription"],
        callback_data=AdminProlongSubscriptionCb(tg_id=int(target_tg_id)),
    )
    kb.button(
        text=cfg["admin_btn"]["cancel_prolong_subscription"],
        callback_data=AdminCancelProlongSubscriptionCb(tg_id=int(target_tg_id)),
    )
    kb.button(text=cfg["admin_btn"]["proccess_search_wair_confirm"], callback_data="search_by_username_id")
    kb.button(text=cfg["admin_btn"]["back_to_wait_confirm_menu"], callback_data="wait_confirm")
    kb.adjust(1)
    return kb

async def subscription_settings_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в настройках подписки
    """
    cfg = await get_config_lang(lang)
    subscription_status = await db.get_subscription_status(user_id)
    kb = InlineKeyboardBuilder()
    if subscription_status:
        kb.button(text=cfg["admin_btn"]["edit_subscription_false_mode"], callback_data="edit_subscription_mode")
    else:
        kb.button(text=cfg["admin_btn"]["edit_subscription_true_mode"], callback_data="edit_subscription_mode")
    kb.button(text=cfg["admin_btn"]["edit_date_end_subs"], callback_data="edit_date_end_subs")
    kb.button(text=cfg["admin_btn"]["back_to_subscriber_card"], callback_data="subscribers_settings_main")
    kb.adjust(1)
    return kb

async def back_to_subscription_settings_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки при возврате в настройках подписки
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="subscription_settings")
    kb.adjust(1)
    return kb

async def bybit_settings_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в настройках клиента ByBit
    """
    cfg = await get_config_lang(lang)
    user = await db.get_user(user_id)
    stop_trading = False
    if user is not None:
        stop_trading = (user.get("bybit_data") or {}).get("stop_trading") is True

    kb = InlineKeyboardBuilder()
    kb.button(text=cfg["admin_btn"]["edit_api_key"], callback_data="edit_api_key")
    kb.button(text=cfg["admin_btn"]["edit_api_secret"], callback_data="edit_api_secret")
    kb.button(text=cfg["admin_btn"]["edit_sum_for_trades"], callback_data="edit_sum_for_trades")
    if stop_trading:
        kb.button(text=cfg["admin_btn"]["edit_stop_trading_resume_mode"], callback_data="edit_stop_trades")
    else:
        kb.button(text=cfg["admin_btn"]["edit_stop_trading_stop_mode"], callback_data="edit_stop_trades")
    kb.button(text=cfg["admin_btn"]["back_to_subscriber_card"], callback_data="subscribers_settings_main")
    kb.adjust(1)
    return kb

async def back_to_bybit_settings_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки при изменения API key
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="bybit_settings")
    kb.adjust(1)
    return kb

async def statistics_info_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в статистике подписчика
    """
    cfg = await get_config_lang(lang)
    kb = InlineKeyboardBuilder()
    kb.button(text=cfg["admin_btn"]["back_to_subscriber_card"], callback_data="subscribers_settings_main")
    kb.adjust(1)
    return kb