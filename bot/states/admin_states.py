from aiogram.fsm.state import State, StatesGroup

class AdminStates(StatesGroup):
    wait_confirm_user = State()      # ожидающие подтверждения
    subscribers_user = State()      # подписчики
    edit_end_subscription_date = State()  # редактирование даты окончания подписки