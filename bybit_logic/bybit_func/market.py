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
    min_qty = float(response.get('result', {}).get('list', [])[0].get('lotSizeFilter', {}).get('minOrderQty'))
    step_size = float(response.get('result', {}).get('list', [])[0].get('lotSizeFilter', {}).get('qtyStep'))
    return min_qty, step_size

def get_price_limits(symbol, session: HTTP):
    response = session.get_instruments_info(
        category="linear",
        symbol=symbol,
    )
    price_filter = response.get('result', {}).get('list', [])[0].get('priceFilter', {})
    min_price = float(price_filter.get('minPrice', 0))
    tick_size = float(price_filter.get('tickSize', 0))
    return min_price, tick_size