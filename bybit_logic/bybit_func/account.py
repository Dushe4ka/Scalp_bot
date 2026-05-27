from pybit.unified_trading import HTTP

def get_futures_balance(session: HTTP) -> float:
    balance = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
    usdt_futures = balance['result']['list'][0]['coin'][0]['walletBalance']
    return float(usdt_futures)

def get_spot_balance(session: HTTP) -> float:
    balance = session.get_wallet_balance(accountType="SPOT", coin="USDT")
    usdt_spot = balance['result']['list'][0]['coin'][0]['walletBalance']
    return float(usdt_spot)