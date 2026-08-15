from pybit.unified_trading import HTTP

def get_tickers_by_symbol(session: HTTP, symbol: str) -> dict:
    return session.get_tickers(
        category="linear",
        symbol=symbol
    )

def get_qty_limits(symbol, session: HTTP):
    response = session.get_instruments_info(
        category="linear",
        symbol=symbol,
    )
    lot_size_filter = response.get('result', {}).get('list', [])[0].get('lotSizeFilter', {})
    min_qty = float(lot_size_filter.get('minOrderQty'))
    step_size = float(lot_size_filter.get('qtyStep'))
    max_qty = float(lot_size_filter.get('maxOrderQty'))
    return min_qty, step_size, max_qty

def get_price_limits(symbol, session: HTTP):
    response = session.get_instruments_info(
        category="linear",
        symbol=symbol,
    )
    price_filter = response.get('result', {}).get('list', [])[0].get('priceFilter', {})
    min_price = float(price_filter.get('minPrice', 0))
    tick_size = float(price_filter.get('tickSize', 0))
    return min_price, tick_size