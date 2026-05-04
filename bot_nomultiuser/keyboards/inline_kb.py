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
    kb.button(text="🔴 Custom Algo", callback_data="custom_algo_launch")
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
    kb.button(text="Custom ⚙️", callback_data="custom_algo")
    kb.button(text="⬅️ Назад", callback_data="trading")
    kb.adjust(1)
    return kb


def custom_algo_config_kb(config: dict) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    direction = config.get("direction", "long")
    direction_label = "Лонг" if direction == "long" else "Шорт"
    mark = lambda enabled: "✅" if enabled else "❌"

    kb.button(text=f"0. Сторона: {direction_label}", callback_data="custom_toggle_direction")
    kb.button(
        text=f"1. Трейлинг стоп: {mark(config.get('use_trailing_stop', False))}",
        callback_data="custom_toggle_trailing",
    )
    kb.button(
        text=f"2. Стоп-лосс: {mark(config.get('use_stop_loss', False))}",
        callback_data="custom_toggle_stop_loss",
    )
    kb.button(
        text=f"3. БУ: {mark(config.get('use_breakeven', False))}",
        callback_data="custom_toggle_breakeven",
    )
    amount = config.get("order_amount_usdt")
    amount_text = f"{amount:g} USDT" if isinstance(amount, (float, int)) else "10 USDT"
    kb.button(text=f"4. Цена ордера: {amount_text}", callback_data="custom_set_order_amount")
    kb.button(text="5. Далее", callback_data="custom_next")
    kb.button(text="⬅️ Назад", callback_data="algorithms")
    kb.adjust(1)
    return kb


def custom_algo_saved_kb() -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.button(text="Изменить", callback_data="custom_algo_edit")
    kb.button(text="⬅️ Назад", callback_data="algorithms")
    kb.adjust(1)
    return kb


def custom_algo_confirm_kb() -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Принять", callback_data="custom_confirm_accept")
    kb.button(text="⬅️ Назад", callback_data="custom_confirm_back")
    kb.adjust(2)
    return kb


def custom_step_back_kb() -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="custom_step_back")
    return kb


def custom_launch_amount_back_kb() -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="custom_launch_back_to_symbol")
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