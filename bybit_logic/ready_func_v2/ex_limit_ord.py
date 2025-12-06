from bybit_logic.bybit_func import session, orders, position, calculator
from bybit_logic.bybit_func.market import get_qty_limits
import os
import dotenv

dotenv.load_dotenv()

SYMBOL = os.getenv("SYMBOL").upper()
USDT_AMOUNT = float(os.getenv("USDT_AMOUNT"))
POSITION_SIDE = os.getenv("POSITION_SIDE")
LIMIT_PERCENTAGE = float(os.getenv("LIMIT_PERCENTAGE"))

session = session.create_session()

# 1. Рассчитываем qty для маркетного ордера
qty_market = calculator.calculate_qty(SYMBOL, USDT_AMOUNT, session)
print(f"📊 Qty для маркетного ордера: {qty_market}")

print("🟢 Размещаем маркетный ордер...")
place_market_order = orders.place_order(SYMBOL, qty_market, POSITION_SIDE, "Market", session)
print(f"place_market_order: {place_market_order}")

# 2. Получаем цену входа позиции
position_info = position.get_last_position_by_symbol(session, SYMBOL)
position_price = float(position_info['avgPrice'])
print(f"💰 Цена входа позиции: {position_price}")

# 3. Рассчитываем лимитную цену
limit_price = calculator.calculate_limit_price(position_price, LIMIT_PERCENTAGE, POSITION_SIDE)
print(f"🎯 Лимитная цена: {limit_price} ({LIMIT_PERCENTAGE}% от {position_price})")

# 4. ✅ ПРАВИЛЬНО: Рассчитываем qty для лимитного ордера на основе лимитной цены
qty_limit = USDT_AMOUNT / limit_price
print(f"📊 Рассчитанное qty для лимитного ордера: {qty_limit}")

# 5. Округляем qty с учетом лимитов биржи
min_qty, step_size = get_qty_limits(SYMBOL, session)
if qty_limit < min_qty:
    qty_limit = min_qty
qty_limit = calculator.round_by_step(qty_limit, step_size)

print(f"📊 Округленное qty для лимитного ордера: {qty_limit}")
print(f"💰 Объем лимитного ордера в USDT: {qty_limit * limit_price:.2f} USDT")

print("🟢 Размещаем лимитный ордер...")
place_limit_order = orders.place_limit_order(SYMBOL, qty_limit, POSITION_SIDE, limit_price, session)
print(f"place_limit_order: {place_limit_order}")