from aiogram.fsm.state import State, StatesGroup

class TradingStates(StatesGroup):
    waiting_for_symbol = State()
    waiting_for_stop_symbol = State()
    waiting_for_info_symbol = State()

