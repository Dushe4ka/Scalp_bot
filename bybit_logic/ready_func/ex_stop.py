from bybit_logic.bybit_func import session, stop_trade

session = session.create_session()
result = stop_trade.stop_all_trading(session)
print(result)