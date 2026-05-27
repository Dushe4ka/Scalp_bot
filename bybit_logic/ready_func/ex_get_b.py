from bybit_logic.bybit_func import session, account
from bybit_logic.bybit_func.calculator import calculate_max_permitted_price
session = session.create_session(use_demo=False)

balance = account.get_futures_balance(session)
max_permitted_price = calculate_max_permitted_price(balance)
print(balance)
print(max_permitted_price)