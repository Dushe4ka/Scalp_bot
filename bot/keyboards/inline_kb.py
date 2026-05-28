from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.languages._lang_func import get_config_lang
from bot.callback_data.admin_lists import (
    ADMIN_LIST_PAGE_SIZE,
    ActiveTradeItemCb,
    ActiveTradesPageCb,
    HISTORY_TRADES_PAGE_SIZE,
    HistoryTradeItemCb,
    HistoryTradesPageCb,
    SubscribersListPageCb,
    SubscribersUserCb,
    WaitConfirmListPageCb,
    WaitConfirmUserCb,
)
from database.users_repository import db
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

def russia_start_kb(user_id: int) -> InlineKeyboardBuilder:
    """
    Русское меню кнопок после выбора языка (start)
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="Наш ТГ канал", url=URL_TGCHANNEL)
    kb.button(text="Личный кабинет", callback_data="profile_menu")
    kb.button(text="Приобрести подписку", callback_data="subscription_buy")
    kb.button(text="Назад", callback_data="start_menu")
    kb.adjust(1)
    return kb

def russia_start_kb_wait_confirm_subscription(user_id: int) -> InlineKeyboardBuilder:
    """
    Русское меню кнопок после выбора языка (start) без подписки
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="Наш ТГ канал", url=URL_TGCHANNEL)
    kb.button(text="Личный кабинет", callback_data="profile_menu")
    kb.button(text="Назад", callback_data="start_menu")
    kb.adjust(1)
    return kb

def russia_start_kb_with_subscription(user_id: int) -> InlineKeyboardBuilder:
    """
    Русское меню кнопок после выбора языка (start) с подпиской
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="Наш ТГ канал", url=URL_TGCHANNEL)
    kb.button(text="Личный кабинет", callback_data="profile_menu")
    kb.button(text="Продлить подписку", callback_data="prolong_subscription")
    kb.button(text="Назад", callback_data="start_menu")
    kb.adjust(1)
    return kb

def english_start_kb(user_id: int) -> InlineKeyboardBuilder:
    """
    Английское меню кнопок после выбора языка (start)
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="Our TG channel", url=URL_TGCHANNEL)
    kb.button(text="Profile", callback_data="profile_menu")
    kb.button(text="Buy subscription", callback_data="subscription_buy")
    kb.button(text="Back", callback_data="start_menu")
    kb.adjust(1)
    return kb

def english_start_kb_wait_confirm_subscription(user_id: int) -> InlineKeyboardBuilder:
    """
    Английское меню кнопок после выбора языка (start) без подписки
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="Our TG channel", url=URL_TGCHANNEL)
    kb.button(text="Profile", callback_data="profile_menu")
    kb.button(text="Back", callback_data="start_menu")
    kb.adjust(1)
    return kb

def english_start_kb_with_subscription(user_id: int) -> InlineKeyboardBuilder:
    """
    Английское меню кнопок после выбора языка (start) с подпиской
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="Our TG channel", url=URL_TGCHANNEL)
    kb.button(text="Profile", callback_data="profile_menu")
    kb.button(text="Prolong subscription", callback_data="prolong_subscription")
    kb.button(text="Back", callback_data="start_menu")
    kb.adjust(1)
    return kb

async def greeting_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Меню кнопок после выбора языка (greeting)
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["start_btn"]["url_tg"], url=URL_TGCHANNEL)
    kb.button(text=(await get_config_lang(lang))["start_btn"]["personal_account"], callback_data="profile_menu")
    kb.button(text=(await get_config_lang(lang))["start_btn"]["subscription_buy"], callback_data="subscription_buy")
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="start_menu")
    kb.adjust(1)
    return kb

async def greeting_kb_wait_confirm_subscription(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Меню кнопок после выбора языка (greeting) ожидания подтверждения подписки
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["start_btn"]["url_tg"], url=URL_TGCHANNEL)
    kb.button(text=(await get_config_lang(lang))["start_btn"]["personal_account"], callback_data="profile_menu")
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="start_menu")
    kb.adjust(1)
    return kb

async def greeting_kb_with_subscription(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Меню кнопок после выбора языка (greeting) с подпиской
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["start_btn"]["url_tg"], url=URL_TGCHANNEL)
    kb.button(text=(await get_config_lang(lang))["start_btn"]["personal_account"], callback_data="profile_menu")
    kb.button(text=(await get_config_lang(lang))["start_btn"]["prolong_subscription"], callback_data="prolong_subscription")
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="start_menu")
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
    Кнопки перехода в профиль после оплаты подписки
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="greeting")
    kb.adjust(1)
    return kb

# -------------------------------------------------------------
# Profile keyboards
# -------------------------------------------------------------

async def profile_menu_kb_without_subscription(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в профиле без подписки
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["profile_btn"]["subscription_buy"], callback_data="subscription_buy")
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="greeting")
    kb.adjust(1)
    return kb

async def profile_menu_wait_sub_confirmation_kb_with_subscription(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в профиле ожидания подтверждения подписки с подпиской
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["profile_btn"]["statistics"], callback_data="statistics")
    kb.button(text=(await get_config_lang(lang))["profile_btn"]["settings_profile"], callback_data="settings_profile")
    kb.button(text=(await get_config_lang(lang))["profile_btn"]["trading"], callback_data="trading")
    kb.button(text=(await get_config_lang(lang))["profile_btn"]["trading_portfolio"], callback_data="trading_portfolio")
    kb.button(text=(await get_config_lang(lang))["profile_btn"]["history_trades"], callback_data="history_trades")
    kb.button(text=(await get_config_lang(lang))["profile_btn"]["tech_support"], url=URL_TECH_SUPPORT)
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="greeting")
    kb.adjust(1)
    return kb

async def profile_menu_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в профиле с подпиской без ожидания подтверждения подписки
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["profile_btn"]["statistics"], callback_data="statistics")
    kb.button(text=(await get_config_lang(lang))["profile_btn"]["settings_profile"], callback_data="settings_profile")
    kb.button(text=(await get_config_lang(lang))["profile_btn"]["trading"], callback_data="trading")
    kb.button(text=(await get_config_lang(lang))["profile_btn"]["trading_portfolio"], callback_data="trading_portfolio")
    kb.button(text=(await get_config_lang(lang))["profile_btn"]["history_trades"], callback_data="history_trades")
    kb.button(text=(await get_config_lang(lang))["profile_btn"]["tech_support"], url=URL_TECH_SUPPORT)
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="greeting")
    kb.adjust(1)
    return kb

async def profile_menu_wait_sub_confirmation_kb_without_subscription(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в профиле ожидания подтверждения подписки без подписки
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["profile_btn"]["tech_support"], url=URL_TECH_SUPPORT)
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="greeting")
    kb.adjust(1)
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
    """
    Кнопки в настройках профиля
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["profile_btn"]["edit_api_key_secret"], callback_data="profile_settings_api_key_secret")
    kb.button(text=(await get_config_lang(lang))["profile_btn"]["edit_sum_for_trades"], callback_data="profile_settings_sum_for_trades")
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="profile_menu")
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
    kb.adjust(1)
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
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["admin_btn"]["users_list"], callback_data="users_list")
    kb.button(text=(await get_config_lang(lang))["admin_btn"]["statistics_project"], callback_data="statistics_project")
    kb.button(text=(await get_config_lang(lang))["admin_btn"]["stop_all_trading"], callback_data="admin_stop_all_trading")
    kb.button(text=(await get_config_lang(lang))["admin_btn"]["server"], callback_data="server")
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="greeting")
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
    kb.button(text=cfg["admin_btn"]["confirm_subscription"], callback_data="confirm_subscription")
    kb.button(text=(await get_config_lang(lang))["admin_btn"]["cancel_subscription"], callback_data="cancel_subscription")
    kb.button(text=cfg["admin_btn"]["proccess_search_wair_confirm"], callback_data="search_by_username_id")
    kb.button(text=cfg["admin_btn"]["back_menu_wait_confirm"], callback_data="wait_confirm")
    kb.adjust(1)
    return kb

async def positive_proccess_search_subscribers_kb(
    lang: str,
    *,
    from_subscribers_list: bool = False,
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
    kb.button(text=cfg["admin_btn"]["proccess_search_wair_confirm"], callback_data="search_subscribers_by_username_id")
    kb.button(text=cfg["admin_btn"]["back_menu_wait_confirm"], callback_data="subscribers")
    kb.adjust(1)
    return kb

async def positive_proccess_search_wait_confirm_user_kb_with_subscription(
    lang: str,
    *,
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
    kb.button(text=cfg["admin_btn"]["prolong_subscription"], callback_data="admin_prolong_subscription")
    kb.button(text=cfg["admin_btn"]["cancel_prolong_subscription"], callback_data="cancel_prolong_subscription")
    kb.button(text=cfg["admin_btn"]["proccess_search_wair_confirm"], callback_data="search_by_username_id")
    kb.button(text=cfg["admin_btn"]["back_menu_wait_confirm"], callback_data="wait_confirm")
    kb.adjust(1)
    return kb

async def subscription_settings_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в настройках подписки
    """
    subscription_status = await db.get_subscription_status(user_id)
    kb = InlineKeyboardBuilder()
    if subscription_status:
        kb.button(text=(await get_config_lang(lang))["admin_btn"]["edit_subscription_false_mode"], callback_data="edit_subscription_mode")
    else:
        kb.button(text=(await get_config_lang(lang))["admin_btn"]["edit_subscription_true_mode"], callback_data="edit_subscription_mode")
    kb.button(text=(await get_config_lang(lang))["admin_btn"]["edit_date_end_subs"], callback_data="edit_date_end_subs")
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="subscribers_settings_main")
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
    kb.button(text=cfg["general"]["back"], callback_data="subscribers_settings_main")
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
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["admin_btn"]["trading_list"], callback_data="trading_list")
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="subscribers_settings_main")
    kb.adjust(1)
    return kb