from bybit_logic.bybit_func import session, position, market, calculator, orders
import os
import dotenv

dotenv.load_dotenv()

SYMBOL = os.getenv("SYMBOL").upper()
USDT_AMOUNT = float(os.getenv("USDT_AMOUNT"))
POSITION_SIDE = os.getenv("POSITION_SIDE")

session = session.create_session()

print("🟢 Размещаем 1 ордер...")
calculate_qty = calculator.calculate_qty(SYMBOL, USDT_AMOUNT, session)
place_order = orders.place_order(SYMBOL, calculate_qty, POSITION_SIDE, "Market", session)
result_position = position.get_last_position_by_symbol(session, SYMBOL)
print(f"result_position: {result_position}")

# print("🟢 Размещаем 2 ордер...")
# place_order_2 = orders.place_order(SYMBOL, calculate_qty, POSITION_SIDE, "Market", session)
# result_position_2 = position.get_last_position_by_symbol(session, SYMBOL)
# print(f"result_position_2: {result_position_2}")