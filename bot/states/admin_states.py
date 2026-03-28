from aiogram.fsm.state import State, StatesGroup

class AdminStates(StatesGroup):
    wait_confirm_user = State()      # ожидающие подтверждения
    subscribers_user = State()      # подписчики
    edit_end_subscription_date = State()  # редактирование даты окончания подписки
    edit_bybit_api_key = State()
    edit_bybit_api_secret = State()
    edit_bybit_sum_for_trades = State()