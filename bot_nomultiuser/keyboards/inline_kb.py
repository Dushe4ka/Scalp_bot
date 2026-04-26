from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import is_subscriber

def main_menu_kb(user_id: int) -> InlineKeyboardBuilder:
    """
    Главное меню кнопок
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="🔔 Подписка", callback_data="subscription")
    kb.button(text="🖥 Сервер", callback_data="server")
    kb.button(text="📈 Трейдинг", callback_data="trading")
    kb.button(text="👤 Аккаунт", callback_data="account")
    kb.adjust(1)
    return kb

def subscription_kb(user_id: int) -> InlineKeyboardBuilder:
    """
    Меню подписки
    """
    kb = InlineKeyboardBuilder()
    if is_subscriber(user_id):
        kb.button(text="❌ Отписаться", callback_data="unsubscribe")
    else:
        kb.button(text="✅ Подписаться", callback_data="subscribe")
    kb.button(text="⬅️ Назад", callback_data="main_menu")
    kb.adjust(1)
    return kb

def server_kb() -> InlineKeyboardBuilder:
    """
    Меню сервера
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="🔍 Проверка работоспособности", callback_data="check_health")
    kb.button(text="⬅️ Назад", callback_data="main_menu")
    kb.adjust(1)
    return kb

def trading_kb() -> InlineKeyboardBuilder:
    """
    Меню трейдинга
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="🤖 Алгоритмы", callback_data="algorithms")
    kb.button(text="🛑 Остановка трейдинга", callback_data="stop_trading")
    kb.button(text="💰 Информация о позиции", callback_data="result_position_info")
    kb.button(text="⬅️ Назад", callback_data="main_menu")
    kb.adjust(1)
    return kb

def algorithms_kb() -> InlineKeyboardBuilder:
    """
    Меню алгоритмов
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="Short BU TS limit (nomulti)", callback_data="nomulti_short_bu_ts_limit")
    kb.button(text="Hedge long + short", callback_data="hedge_long_short_bu_ts")
    kb.button(text="⬅️ Назад", callback_data="trading")
    kb.adjust(1)
    return kb

def stop_trading_kb() -> InlineKeyboardBuilder:
    """
    Меню остановки трейдинга
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="По названию монеты", callback_data="stop_by_symbol")
    kb.button(text="Вся торговля", callback_data="stop_trading_all")
    kb.button(text="⬅️ Назад", callback_data="trading")
    kb.adjust(1)
    return kb

def back_to_main_kb() -> InlineKeyboardBuilder:
    """
    Кнопка назад в главное меню
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="main_menu")
    return kb

def account_kb() -> InlineKeyboardBuilder:
    """
    Меню аккаунта
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="💰 Баланс", callback_data="account_balance")
    kb.button(text="⬅️ Назад", callback_data="main_menu")
    kb.adjust(1)
    return kb

def account_balance_kb() -> InlineKeyboardBuilder:
    """
    Меню баланса аккаунта
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="💰 Futures", callback_data="account_balance_futures")
    kb.button(text="⬅️ Назад", callback_data="account")
    kb.adjust(1)
    return kb

def result_position_info_kb() -> InlineKeyboardBuilder:
    """
    Кнопка информации о позиции
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="По названию монеты", callback_data="result_position_info_by_symbol")
    kb.button(text="⬅️ Назад", callback_data="trading")
    kb.adjust(1)
    return kb