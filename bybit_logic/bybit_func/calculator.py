from bybit_logic.bybit_func.market import get_tickers_by_symbol, get_qty_limits
from pybit.unified_trading import HTTP
import math
from decimal import Decimal, ROUND_DOWN

def round_by_step(value: float, step: float) -> float:
    """
    Округляет значение до ближайшего кратного step вниз
    Использует Decimal для точности
    """
    if step == 0:
        return value
    
    # Используем Decimal для точных вычислений
    value_decimal = Decimal(str(value))
    step_decimal = Decimal(str(step))
    
    # Округляем вниз до ближайшего кратного step
    rounded = (value_decimal / step_decimal).quantize(Decimal('1'), rounding=ROUND_DOWN) * step_decimal
    
    return float(rounded)

def USDT_to_qty(usdt: float, symbol: str, session: HTTP) -> float:
    ticker = get_tickers_by_symbol(session, symbol)
    return usdt / float(ticker['result']['list'][0]['lastPrice'])

def calculate_qty(symbol, usdt_amount, session: HTTP):
    ticker = get_tickers_by_symbol(session, symbol)
    last_price = float(ticker['result']['list'][0]['lastPrice'])
    
    qty = usdt_amount / last_price
    min_qty, step_size = get_qty_limits(symbol, session)
    
    if qty < min_qty:
        qty = min_qty
    
    qty = round_by_step(qty, step_size)
    
    # ✅ Дополнительное округление до нужного количества знаков после запятой
    # Определяем количество знаков после запятой из step_size
    if step_size >= 1:
        decimal_places = 0
    else:
        # Считаем количество знаков после запятой в step_size
        step_str = str(step_size).rstrip('0')
        if '.' in step_str:
            decimal_places = len(step_str.split('.')[1])
        else:
            decimal_places = 0
    
    # Округляем до нужного количества знаков
    qty = round(qty, decimal_places)
    
    return qty

def calculate_stop_loss(entry_price: float, stop_loss_percentage: float, side: str = "Buy") -> float:
    if side == "Buy":
        return entry_price * (100 - stop_loss_percentage) / 100
    else:
        return entry_price * (100 + stop_loss_percentage) / 100

def calculate_little_less_price(price: float, percentage: float, side: str = "Buy") -> float:
    if side == "Buy":
        return price * (100 - percentage) / 100
    else:
        return price * (100 + percentage) / 100

def calculate_limit_price(price: float, percentage: float, side: str = "Buy") -> float:
    if side == "Buy":
        return price * (100 - percentage) / 100
    else:
        return price * (100 + percentage) / 100