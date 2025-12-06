from bybit_logic.bybit_func import session, orders, calculator, position
import os
import dotenv

dotenv.load_dotenv()

SYMBOL = os.getenv("SYMBOL").upper()
USDT_AMOUNT = float(os.getenv("USDT_AMOUNT"))
POSITION_SIDE = os.getenv("POSITION_SIDE")
LIMIT_PERCENTAGE = float(os.getenv("LIMIT_PERCENTAGE"))
N = int(os.getenv("COUNT_LIMIT_ORDERS"))

session = session.create_session()

qty = calculator.calculate_qty(SYMBOL, USDT_AMOUNT, session)
print(f"qty: {qty}")

place_order = orders.place_order(SYMBOL, qty, POSITION_SIDE, "Market", session)
print(f"place_order: {place_order}")

position_info = position.get_last_position_by_symbol(session, SYMBOL)
position_price = float(position_info['avgPrice'])
print(f"position_price: {position_price}")

place_n_limit_order = orders.place_n_limit_order(SYMBOL, qty, POSITION_SIDE, position_price, session, N, LIMIT_PERCENTAGE)
print(f"place_n_limit_order: {place_n_limit_order}")