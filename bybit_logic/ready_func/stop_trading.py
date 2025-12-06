from pybit.unified_trading import HTTP
from bybit_logic.bybit_func import session, stop_trade
from dotenv import load_dotenv
import os

load_dotenv()

SYMBOL = os.getenv("SYMBOL").upper()

session = session.create_session()

# # 1. Остановить всю торговлю
# stop_trade.stop_all_trading(session)

# 2. Остановить торговлю для конкретной монеты
stop_trade.stop_trading_by_symbol(SYMBOL, session)

# # 3. Только отменить ордера для конкретной монеты
# stop_trade.cancel_orders_by_symbol(SYMBOL, session)

# # 4. Только закрыть позицию для конкретной монеты
# stop_trade.close_position_by_symbol(SYMBOL, session)