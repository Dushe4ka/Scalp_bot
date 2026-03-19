from aiogram.fsm.state import State, StatesGroup

class SubscriptionStates(StatesGroup):
    waiting_payment_id = State()   # ждём ввод ID платежа
    waiting_confirm = State()      # ждём Да/Нет после показа "Всё верно"