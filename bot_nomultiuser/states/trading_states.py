from aiogram.fsm.state import State, StatesGroup

class TradingStates(StatesGroup):
    waiting_for_symbol = State()
    waiting_for_stop_symbol = State()
    waiting_for_info_symbol = State()
    waiting_for_custom_trailing_step = State()
    waiting_for_custom_trailing_activate = State()
    waiting_for_custom_stop_loss = State()
    waiting_for_custom_breakeven = State()
    waiting_for_custom_order_amount = State()
    waiting_for_custom_launch_symbol = State()
    waiting_for_custom_launch_amount = State()

