from aiogram.fsm.state import State, StatesGroup


class ProfileStates(StatesGroup):
    edit_api_key = State()
    edit_api_secret = State()
    edit_sum_for_trades = State()
