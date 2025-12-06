from bybit_logic.bybit_func import session, position, market, calculator, orders

USDT_AMOUNT = 1000
STOP_LOSS_PERCENTAGE = 4
LIMIT_STOP_LOSS_PERCENTAGE = 2
session = session.create_session()
SYMBOL = "KGENUSDT"

# Получаем последнюю цену
tickers = market.get_tickers_by_symbol(session, SYMBOL)
last_price = tickers['result']['list'][0]['lastPrice']
print(f"last_price: {last_price}")

# Рассчитываем количество монет
calculate_qty = calculator.calculate_qty(SYMBOL, USDT_AMOUNT, session)
print(f"calculate_qty: {calculate_qty}")

# Размещаем ордер
place_order = orders.place_order(SYMBOL, calculate_qty, "Buy", "Market", session)
print(place_order)

# Получаем цену позиции
position_price = position.get_positions_by_symbol(session, SYMBOL)
position_price = float(position_price['result']['list'][0]['avgPrice'])
print(f"position_price: {position_price}")

# Рассчитываем stop loss
stop_loss_price = calculator.calculate_stop_loss(position_price, STOP_LOSS_PERCENTAGE, "Buy")
print(f"position_price: {position_price}, stop_loss_price: {stop_loss_price}")

# Получаем минимальное количество монет и шаг
min_qty, step_size = market.get_qty_limits(SYMBOL, session)
print(f"min_qty: {min_qty}, step_size: {step_size}")

# Получаем шаг цены для округления стоп-лосса
min_price, tick_size = market.get_price_limits(SYMBOL, session)
print(f"min_price: {min_price}, tick_size: {tick_size}")

# Округляем stop loss до шага ЦЕНЫ (не количества!)
calc_sl_price = calculator.round_by_step(stop_loss_price, tick_size)
print(f"calc_sl_price: {calc_sl_price}")

# Устанавливаем stop loss
set_stop_loss = orders.set_stop_loss(SYMBOL, calc_sl_price, session)
print(set_stop_loss)

# Рассчитываем limit stop loss
limit_stop_loss_price = calculator.calculate_limit_stop_loss(position_price, LIMIT_STOP_LOSS_PERCENTAGE, "Buy")
print(f"position_price: {position_price}, limit_stop_loss_price: {limit_stop_loss_price}")

# Устанавливаем limit stop loss
set_limit_stop_loss = orders.set_limit_stop_loss(SYMBOL, limit_stop_loss_price, session)
print(set_limit_stop_loss)