from bybit_logic.bybit_func import session, position, market, calculator, orders
import os
import dotenv

dotenv.load_dotenv()

SYMBOL = os.getenv("SYMBOL").upper()
USDT_AMOUNT = float(os.getenv("USDT_AMOUNT"))
TRIGGER_PERCENTAGE = float(os.getenv("TRIGGER_PERCENTAGE"))
POSITION_SIDE = os.getenv("POSITION_SIDE")
USE_DEMO = bool(os.getenv("USE_DEMO"))
PNL_LOG_INTERVAL = float(os.getenv("PNL_LOG_INTERVAL"))

session = session.create_session()

positions = position.get_positions_by_symbol(session, SYMBOL)
position_price = positions['result']['list'][0]['avgPrice']
position_mark_price = positions['result']['list'][0]['markPrice']
print(f"position_price: {position_price}, position_mark_price: {position_mark_price}")
try:
    if POSITION_SIDE == "Buy":
        if position_mark_price > position_price:
            orders.set_stop_loss(SYMBOL, position_mark_price, session)
            print(f"Stop loss set to {position_mark_price}")
    else:
        if position_mark_price < position_price:
            orders.set_stop_loss(SYMBOL, position_mark_price, session)
            print(f"Stop loss set to {position_mark_price}")
except Exception as e:
    print(f"Error: {e}")