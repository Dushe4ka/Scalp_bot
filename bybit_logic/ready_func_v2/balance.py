from bybit_logic.bybit_func.session import create_session

session = create_session(use_demo=False)

futures_balance = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
usdt_futures = futures_balance['result']['list'][0]['coin'][0]['walletBalance']
print(f"Futures USDT: {usdt_futures}")